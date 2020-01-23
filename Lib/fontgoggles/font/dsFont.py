import numpy
from fontTools.pens.basePen import BasePen


class PointCollector(BasePen):

    def __init__(self, glyphSet):
        super().__init__(glyphSet)
        self.points = []

    def moveTo(self, pt):
        self.points.append(pt)

    lineTo = moveTo

    def curveTo(self, *pts):
        self.points.extend(pts)

    def qCurveTo(self, *pts):
        if pts[-1] is None:
            pts = pts[:-1]
        self.points.extend(pts)

    def getPointsArray(self, tp=numpy.float32):
        return numpy.array(self.points, tp)


# From FreeType:
FT_CURVE_TAG_ON = 1
FT_CURVE_TAG_CONIC = 0
FT_CURVE_TAG_CUBIC = 2


class PointAndStructureCollector(BasePen):

    def __init__(self, glyphSet):
        super().__init__(glyphSet)
        self.points = []
        self.tags = []
        self.contours = []

    def moveTo(self, pt):
        self.points.append(pt)
        self.tags.append(FT_CURVE_TAG_ON)

    lineTo = moveTo

    def curveTo(self, *pts):
        self.tags.extend([FT_CURVE_TAG_CUBIC] * (len(pts) - 1))
        self.tags.append(FT_CURVE_TAG_ON)
        self.points.extend(pts)

    def qCurveTo(self, *pts):
        self.tags.extend([FT_CURVE_TAG_CONIC] * (len(pts) - 1))
        if pts[-1] is None:
            pts = pts[:-1]
        else:
            self.tags.append(FT_CURVE_TAG_ON)
        self.points.extend(pts)

    def closePath(self):
        self.contours.append(len(self.points) - 1)

    endPath = closePath

    def getPointsArray(self, tp=numpy.float32):
        return numpy.array(self.points, tp)

    def getTagsArray(self):
        return numpy.array(self.tags, numpy.uint8)

    def getContoursArray(self):
        return numpy.array(self.contours, numpy.uint16)
