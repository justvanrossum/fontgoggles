import asyncio
from collections import defaultdict
import io
import os
import pathlib
import pickle
import sys
import tempfile
from types import SimpleNamespace
import numpy
from fontTools.pens.basePen import BasePen
from fontTools.pens.pointPen import PointToSegmentPen
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.ttLib import TTFont
from fontTools.ufoLib import UFOReader
from fontTools.varLib.models import normalizeValue
from .baseFont import BaseFont
from .ufoFont import NotDefGlyph, extractIncludedFeatureFiles
from ..compile.compilerPool import compileUFOToPath, compileDSToBytes, CompilerError
from ..compile.dsCompiler import getTTPaths
from ..misc.hbShape import HBShape
from ..misc.properties import cachedProperty
from ..mac.makePathFromOutline import makePathFromArrays


class DesignSpaceSourceError(CompilerError):
    pass


class DSFont(BaseFont):

    def __init__(self, fontPath, fontNumber, dataProvider=None):
        super().__init__(fontPath, fontNumber)
        self._varGlyphs = {}
        self._normalizedLocation = {}
        self._sourceFontData = {}
        self._ufoReaders = {}
        self._ufoGlyphSets = {}

    async def load(self, outputWriter):
        self.doc = DesignSpaceDocument.fromfile(self.fontPath)
        self.doc.findDefault()

        with tempfile.TemporaryDirectory(prefix="fontgoggles_temp") as ttFolder:
            ufoPathToTTPath = getTTPaths(self.doc, ttFolder)
            ufosToCompile = []
            ttPaths = []
            outputs = []
            coros = []
            self._includedFeatureFiles = defaultdict(list)

            for source in self.doc.sources:
                reader = UFOReader(source.path, validate=False)
                for includedFeaFile in extractIncludedFeatureFiles(source.path, reader):
                    self._includedFeatureFiles[includedFeaFile].append((source.path, source.layerName))
                self._ufoReaders[(source.path, source.layerName)] = reader
                self._ufoGlyphSets[(source.path, source.layerName)] = reader.getGlyphSet(layerName=source.layerName)

                if source.layerName is not None:
                    continue

                ufoPath = source.path
                if ufoPath in ufosToCompile:
                    continue
                ttPath = ufoPathToTTPath[ufoPath]
                if ufoPath in self._sourceFontData:
                    with open(ttPath, "wb") as f:
                        f.write(self._sourceFontData[source.path])
                else:
                    ufosToCompile.append(ufoPath)
                    ttPaths.append(ttPath)
                    output = io.StringIO()
                    outputs.append(output)
                    coros.append(compileUFOToPath(ufoPath, ttPath, output.write))

            errors = await asyncio.gather(*coros, return_exceptions=True)
            for ufoPath, exc, output in zip(ufosToCompile, errors, outputs):
                output = output.getvalue()
                if output or exc is not None:
                    outputWriter(f"compile output for {ufoPath}:\n")
                    if output:
                        outputWriter(output)
                    if exc is not None:
                        outputWriter(f"{exc!r}\n")

            if any(errors):
                raise DesignSpaceSourceError(
                    f"Could not build '{os.path.basename(self.fontPath)}': "
                    "some sources did not successfully compile"
                )
            for ufoPath, ttPath in zip(ufosToCompile, ttPaths):
                # Store compiled tt data so we can reuse it to rebuild ourselves
                # without recompiling the source.
                with open(ttPath, "rb") as f:
                    self._sourceFontData[ufoPath] = f.read()

            vfFontData = await compileDSToBytes(self.fontPath, ttFolder, outputWriter)

        f = io.BytesIO(vfFontData)
        self.ttFont = TTFont(f, lazy=True)
        # Nice cookie for us from the worker
        self.masterModel = pickle.loads(self.ttFont["MPcl"].data)
        assert len(self.masterModel.deltaWeights) == len(self.doc.sources)

        self.shaper = HBShape(vfFontData, getHorizontalAdvance=self._getHorizontalAdvance, ttFont=self.ttFont)

    def getExternalFiles(self):
        sourcePaths = [pathlib.Path(source.path) for source in self.doc.sources]
        return sourcePaths + sorted(self._includedFeatureFiles)

    def canReloadWithChange(self, externalFilePath):
        print("DS external file changed:", externalFilePath)
        # TODO:
        # - check for changes in .doc
        # - check for changes in sources
        self.resetCache()
        self._varGlyphs = {}
        return True

    @cachedProperty
    def unitsPerEm(self):
        info = SimpleNamespace()
        reader = self._ufoReaders[(self.doc.default.path, self.doc.default.layerName)]
        reader.readInfo(info)
        return info.unitsPerEm

    def varLocationChanged(self, varLocation):
        self._normalizedLocation = normalizeLocation(self.doc, varLocation or {})

    def _getVarGlyph(self, glyphName):
        varGlyph = self._varGlyphs.get(glyphName)
        if varGlyph is None:
            if glyphName not in self._ufoGlyphSets[(self.doc.default.path, self.doc.default.layerName)]:
                varGlyph = NotDefGlyph(self.unitsPerEm)
            else:
                tags = None
                contours = None
                masterPoints = []
                for source in self.doc.sources:
                    glyphSet = self._ufoGlyphSets[(source.path, source.layerName)]
                    if glyphName not in glyphSet:
                        masterPoints.append(None)
                        continue
                    glyph = glyphSet[glyphName]
                    coll = PointCollector(glyphSet)
                    try:
                        glyph.draw(coll)
                    except Exception as e:
                        print(f"Glyph '{glyphName}' could not be read from '{os.path.basename(source.path)}': {e!r}",
                              file=sys.stderr)
                        masterPoints.append(None)
                    else:
                        masterPoints.append(coll.points + [(glyph.width, 0)])
                        if source is self.doc.default:
                            tags = coll.tags
                            contours = coll.contours

                if tags is None:
                    print(f"Default master glyph '{glyphName}' could not be read", file=sys.stderr)
                    varGlyph = NotDefGlyph(self.unitsPerEm)
                else:
                    varGlyph = VarGlyph(glyphName, self.masterModel, masterPoints, contours, tags)
            self._varGlyphs[glyphName] = varGlyph
        varGlyph.setVarLocation(self._normalizedLocation)
        return varGlyph

    def _getHorizontalAdvance(self, glyphName):
        varGlyph = self._getVarGlyph(glyphName)
        return varGlyph.width

    # TODO: vertical advance, vertical origin

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

    def __init__(self, glyphName, masterModel, masterPoints, contours, tags):
        self.model, masterPoints = masterModel.getSubModel(masterPoints)
        masterPoints = [numpy.array(pts, coordinateType) for pts in masterPoints]
        try:
            self.deltas = self.model.getDeltas(masterPoints)
        except ValueError:
            # outlines are not compatible, fall back to the default master
            print(f"Glyph '{glyphName}' is not interpolatable", file=sys.stderr)
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
    # Adapted from DesignSpaceDocument.normalizeLocation(), which takes axis
    # names, yet we need to work with tags here.
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
