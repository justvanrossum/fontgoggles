import asyncio
import io
from typing import NamedTuple
import sys
import numpy
from fontTools import varLib
from fontTools.pens.basePen import BasePen
from fontTools.pens.cocoaPen import CocoaPen
from fontTools.pens.pointPen import PointToSegmentPen
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib import TTFont, newTable
from fontTools.ufoLib import UFOReader
from fontTools.varLib.models import normalizeValue
from .baseFont import BaseFont
from .ufoFont import NotDefGlyph, compileMinimumFont_captureOutput
from ..misc.hbShape import HBShape
from ..misc.properties import readOnlyCachedProperty
from ..misc.runInPool import runInProcessPool
from ..mac.makePathFromOutline import makePathFromArrays


class DSFont(BaseFont):

    def __init__(self, fontPath):
        super().__init__()
        self._fontPath = fontPath
        self._varGlyphs = {}
        self._normalizedLocation = {}

    async def load(self):
        self.doc = DesignSpaceDocument.fromfile(self._fontPath)
        self.doc.findDefault()

        ufosToCompile = sorted({s.path for s in self.doc.sources if s.layerName is None})

        coros = (runInProcessPool(compileMinimumFont_captureOutput, path) for path in ufosToCompile)
        results = await asyncio.gather(*coros)
        fonts = {}
        for path, (fontData, output, error) in zip(ufosToCompile, results):
            if output or error:
                print("----- ", path, file=sys.stderr)
                print(output, file=sys.stderr)
                print(error, file=sys.stderr)
            f = io.BytesIO(fontData)
            fonts[path] = TTFont(f, lazy=False)  # TODO: https://github.com/fonttools/fonttools/issues/1808

        for source in self.doc.sources:
            if source.layerName is None:
                source.font = fonts[source.path]
            reader = UFOReader(source.path, validate=False)
            source.ufoGlyphSet = reader.getGlyphSet(layerName=source.layerName)
        assert self.doc.default.font is not None
        self.doc.default.font["name"] = newTable("name")  # This is the template for the VF, and needs a name table

        if any(s.layerName is not None for s in self.doc.sources):
            fb = FontBuilder(unitsPerEm=self.doc.default.font["head"].unitsPerEm)
            fb.setupGlyphOrder(self.doc.default.font.getGlyphOrder())
            fb.setupPost()  # This makes sure we store the glyph names
            font = fb.font
            for source in self.doc.sources:
                if source.font is None:
                    source.font = font

        # - varLib.build() should also run in the process pool, but then
        #   we need the raw fontData from the ufo, not ttFont.
        self.ttFont, self.masterModel, _ = varLib.build(self.doc, exclude=['MVAR', 'HVAR', 'VVAR', 'STAT'])
        assert len(self.masterModel.deltaWeights) == len(self.doc.sources)
        f = io.BytesIO()
        self.ttFont.save(f, reorderTables=False)
        vfFontData = f.getvalue()
        self.shaper = HBShape(vfFontData, getAdvanceWidth=self._getAdvanceWidth, ttFont=self.ttFont)

    def varLocationChanged(self, varLocation):
        self._normalizedLocation = normalizeLocation(self.doc, varLocation or {})

    def _getVarGlyph(self, glyphName):
        varGlyph = self._varGlyphs.get(glyphName)
        if varGlyph is None:
            if glyphName not in self.doc.default.ufoGlyphSet:
                varGlyph = NotDefGlyph(self.unitsPerEm)
            else:
                tags = None
                contours = None
                masterPoints = []
                for source in self.doc.sources:
                    if glyphName not in source.ufoGlyphSet:
                        masterPoints.append(None)
                        continue
                    glyph = source.ufoGlyphSet[glyphName]
                    coll = PointCollector(source.ufoGlyphSet)
                    glyph.draw(coll)
                    masterPoints.append(coll.points + [(glyph.width, 0)])
                    if source is self.doc.default:
                        tags = coll.tags
                        contours = coll.contours

                varGlyph = VarGlyph(self.masterModel, contours, masterPoints, tags)
            self._varGlyphs[glyphName] = varGlyph
        varGlyph.setVarLocation(self._normalizedLocation)
        return varGlyph

    def _getAdvanceWidth(self, glyphName):
        varGlyph = self._getVarGlyph(glyphName)
        return varGlyph.width

    def _getOutlinePath(self, glyphName, colorLayers):
        varGlyph = self._getVarGlyph(glyphName)
        return varGlyph.getOutline()


# From FreeType:
FT_CURVE_TAG_ON = 1
FT_CURVE_TAG_CONIC = 0
FT_CURVE_TAG_CUBIC = 2

segmentTypes = {FT_CURVE_TAG_ON: "line", FT_CURVE_TAG_CONIC: "qcurve", FT_CURVE_TAG_CUBIC: "curve"}
coordinateType = numpy.float


def interpolateFromDeltas(model, varLocation, deltas):
    # This is a numpy-specific reimplementation of model.interpolateFromDeltas()
    # that avoids allocation of in-between results.
    # However, so far this is achieving the speedup I had hoped...
    # Perhaps there'll be a better improvement if there are many deltas
    # and/or if the outlines are more complex.
    deltas = deltas
    temp = numpy.zeros(deltas[0].shape, coordinateType)
    v = numpy.zeros(deltas[0].shape, coordinateType)
    scalars = model.getScalars(varLocation)
    for delta, scalar in zip(deltas, scalars):
        if not scalar:
            continue
        if scalar == 1.0:
            contribution = delta
        else:
            numpy.multiply(delta, scalar, temp)
            contribution = temp
        numpy.add(v, contribution, v)
    return v


NUMPY_IN_PLACE = True  # dubious improvement


class VarGlyph:

    def __init__(self, masterModel, contours, masterPoints, tags):
        self.model, masterPoints = masterModel.getSubModel(masterPoints)
        masterPoints = [numpy.array(pts, coordinateType) for pts in masterPoints]
        try:
            self.deltas = self.model.getDeltas(masterPoints)
        except ValueError:
            # outlines are not compatible, fall back to the default master
            self.deltas = [masterPoints[self.model.reverseMapping[0]]]
        self.contours = numpy.array(contours, numpy.short)
        self.tags = numpy.array(tags, numpy.byte)
        self.varLocation = {}
        self._points = None

    def setVarLocation(self, varLocation):
        if varLocation is None:
            varLocation = {}
        if self.varLocation == varLocation:
            return
        self._points = None
        self.varLocation = varLocation

    def getPoints(self):
        if self._points is None:
            if NUMPY_IN_PLACE:
                self._points = interpolateFromDeltas(self.model, self.varLocation, self.deltas)
            else:
                self._points = self.model.interpolateFromDeltas(self.varLocation, self.deltas)
        return self._points

    @property
    def width(self):
        return self.getPoints()[-1][0]

    def getOutline(self):
        return makePathFromArrays(self.getPoints(), self.tags, self.contours)

    def draw(self, pen):
        ppen = PointToSegmentPen(pen)
        startIndex = 0
        points = self.getPoints()
        for endIndex in self.contours:
            lastTag = self.tags[endIndex]
            endIndex += 1
            contourTags = self.tags[startIndex:endIndex]
            contourPoints = points[startIndex:endIndex]
            ppen.beginPath()
            for tag, (x, y) in zip(contourTags, contourPoints):
                if tag == FT_CURVE_TAG_ON:
                    segmentType = segmentTypes[lastTag]
                else:
                    segmentType = None
                ppen.addPoint((x, y), segmentType=segmentType)
                lastTag = tag
            ppen.endPath()
            startIndex = endIndex


class PointCollector(BasePen):

    def __init__(self, glyphSet):
        super().__init__(glyphSet)
        self.points = []
        self.tags = []
        self.contours = []
        self.contourStartPointIndex = None

    def moveTo(self, pt):
        self.contourStartPointIndex = len(self.points)
        self.points.append(pt)
        self.tags.append(FT_CURVE_TAG_ON)

    def lineTo(self, pt):
        self.points.append(pt)
        self.tags.append(FT_CURVE_TAG_ON)

    def curveTo(self, *pts):
        self.tags.extend([FT_CURVE_TAG_CUBIC] * (len(pts) - 1))
        self.tags.append(FT_CURVE_TAG_ON)
        self.points.extend(pts)

    def qCurveTo(self, *pts):
        self.tags.extend([FT_CURVE_TAG_CONIC] * (len(pts) - 1))
        if pts[-1] is None:
            self.contourStartPointIndex = len(self.points)
            pts = pts[:-1]
        else:
            self.tags.append(FT_CURVE_TAG_ON)
        self.points.extend(pts)

    def closePath(self):
        assert self.contourStartPointIndex is not None
        currentPointIndex = len(self.points) - 1
        if (self.contourStartPointIndex != currentPointIndex and
            self.points[self.contourStartPointIndex] == self.points[currentPointIndex] and
            self.tags[self.contourStartPointIndex] == self.tags[currentPointIndex]):
            self.points.pop()
            self.tags.pop()
        self.contours.append(len(self.points) - 1)
        self.contourStartPointIndex = None

    endPath = closePath


def normalizeLocation(doc, location):
    new = {}
    for axis in doc.axes:
        if axis.tag not in location:
            # skipping this dimension it seems
            continue
        value = location[axis.tag]
        # 'anisotropic' location, take first coord only
        if isinstance(value, tuple):
            value = value[0]
        triple = [
            axis.map_forward(v) for v in (axis.minimum, axis.default, axis.maximum)
        ]
        new[axis.tag] = normalizeValue(value, triple)
    return new

