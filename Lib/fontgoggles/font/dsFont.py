import numpy
from fontTools.pens.basePen import BasePen


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
