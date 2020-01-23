import numpy
from fontTools.pens.basePen import BasePen


class PointCollector(BasePen):

    def __init__(self, glyphSet):
        super().__init__(glyphSet)
        self.points = []

    def moveTo(self, pt):
        self.points.append(pt)

    def lineTo(self, pt):
        self.points.append(pt)

    def curveTo(self, *pts):
        self.points.extend(pts)

    def qCurveTo(self, *pts):
        if pts[-1] is None:
            pts = pts[:-1]
        self.points.extend(pts)

    def getPointsArray(self, tp=numpy.float32):
        return numpy.array(self.points, tp)
