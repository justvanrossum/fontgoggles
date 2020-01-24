import asyncio
import io
import numpy
from fontTools import varLib
from fontTools.pens.basePen import BasePen
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib import TTFont, newTable
from .baseFont import BaseFont
from .ufoFont import UFOFont, compileMinimumFont_captureOutput
from ..misc.hbShape import HBShape
from ..misc.properties import readOnlyCachedProperty
from ..misc.runInPool import runInProcessPool


class DSFont(BaseFont):

    def __init__(self, fontPath):
        super().__init__()
        self._fontPath = fontPath

    async def load(self):
        self.doc = DesignSpaceDocument.fromfile(self._fontPath)
        defaultSource = self.doc.findDefault()

        ufosToCompile = sorted({s.path for s in self.doc.sources if s.layerName is None})
        haveFeatureLessSources = any(s.layerName is not None for s in self.doc.sources)

        coros = (runInProcessPool(compileMinimumFont_captureOutput, path) for path in ufosToCompile)
        results = await asyncio.gather(*coros)
        fonts = {}
        for path, (fontData, output, error) in zip(ufosToCompile, results):
            f = io.BytesIO(fontData)
            fonts[path] = TTFont(f, lazy=False)  # TODO: https://github.com/fonttools/fonttools/issues/1808

        for source in self.doc.sources:
            if source.layerName is None:
                source.font = fonts[source.path]
        assert defaultSource.font is not None
        defaultSource.font["name"] = newTable("name")

        if haveFeatureLessSources:
            fb = FontBuilder(unitsPerEm=defaultSource.font["head"].unitsPerEm)  # XXX single source for upm
            fb.setupGlyphOrder(defaultSource.font.getGlyphOrder())
            fb.setupPost()  # This makes sure we store the glyph names
            font = fb.font
            for source in self.doc.sources:
                if source.font is None:
                    source.font = font

        # - varLib.build() should also run in the process pool, but then
        #   we need the raw fontData from the ufo, not ttFont.
        self.ttFont, _, _ = varLib.build(self.doc, exclude=['MVAR', 'HVAR', 'VVAR', 'STAT'])
        f = io.BytesIO()
        self.ttFont.save(f, reorderTables=False)
        vfFontData = f.getvalue()

        # XXX temp
        self.defaultUFO = UFOFont(defaultSource.path)
        await self.defaultUFO.load()
        self.shaper = HBShape(vfFontData, getAdvanceWidth=self.defaultUFO._getAdvanceWidth, ttFont=self.ttFont)

    def _getOutlinePath(self, glyphName, colorLayers):
        # print("---", self._currentVarLocation)
        return self.defaultUFO._getOutlinePath(glyphName, colorLayers)


# From FreeType:
FT_CURVE_TAG_ON = 1
FT_CURVE_TAG_CONIC = 0
FT_CURVE_TAG_CUBIC = 2


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

    def getPointsArray(self, tp=numpy.float32):
        return numpy.array(self.points, tp)

    def getTagsArray(self):
        return numpy.array(self.tags, numpy.uint8)

    def getContoursArray(self):
        return numpy.array(self.contours, numpy.uint16)
