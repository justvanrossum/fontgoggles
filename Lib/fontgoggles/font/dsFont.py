import numpy
from fontTools.pens.basePen import BasePen
from fontTools.designspaceLib import DesignSpaceDocument
from .baseFont import BaseFont
from .ufoFont import UFOFont
from ..misc.properties import readOnlyCachedProperty


class DSFont(BaseFont):

    def __init__(self, fontPath):
        super().__init__()
        self._fontPath = fontPath

    async def load(self):
        self.doc = DesignSpaceDocument.fromfile(self._fontPath)
        defaultSource = self.doc.findDefault()
        # Steps:
        # - load all master ufos, asyncio.gather(...)
        # - for source in self.doc.sources:
        #       source.font = ufo.ttFont
        # - call varLib.build(self.doc)
        # - varLib.build() should also run in the process pool, but then
        #   we need the raw fontData from the ufo, not ttFont.
        # - note ufos may occur more than once in the sources list, we
        #   should only load once.
        self.defaultUFO = UFOFont(defaultSource.path)
        await self.defaultUFO.load()
        # XXX temp
        self.shaper = self.defaultUFO.shaper

    @readOnlyCachedProperty
    def unitsPerEm(self):
        return self.defaultUFO.info.unitsPerEm

    @readOnlyCachedProperty
    def axes(self):
        # TODO: remove this method because self.ttFont will have an 'fvar' table
        axes = {}
        for axis in self.doc.axes:
            axes[axis.tag] = dict(defaultValue=axis.default,
                                  minValue=axis.minimum,
                                  maxValue=axis.maximum,
                                  name=axis.name)
        return axes

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
