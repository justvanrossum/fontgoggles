from typing import Any, NamedTuple, Sequence, Tuple, Union
from fontTools.misc.arrayTools import unionRect


def hasIntersection(rect1, rect2):
    """Return a boolean. If the input rectangles intersect, return
    True, return False if the input rectangles do not intersect.
    """
    (xMin1, yMin1, xMax1, yMax1) = rect1
    (xMin2, yMin2, xMax2, yMax2) = rect2
    return ((xMin1 < xMax2 and xMax1 > xMin2) and
            (yMin1 < yMax2 and yMax1 > yMin2))


Number = Union[int, float]
Rectangle = Tuple[Number, Number, Number, Number]


class RectTree(NamedTuple):

    bounds: Rectangle
    leaf: Any
    left: "RectTree"
    right: "RectTree"

    @classmethod
    def fromSeq(cls, seq: Sequence):
        if len(seq) < 1:
            raise ValueError("can't build a RectTree from an empty list")
        if len(seq) == 1:
            bounds, leaf = seq[0]
            if leaf is None:
                raise ValueError("leaf values can't be None")
            return cls(bounds, leaf, None, None)
        mid = len(seq) // 2
        left = cls.fromSeq(seq[:mid])
        right = cls.fromSeq(seq[mid:])
        bounds = unionRect(left[0], right[0])
        return cls(bounds, None, left, right)
    
    def iterIntersections(self, targetBounds: Rectangle):
        if not hasIntersection(self.bounds, targetBounds):
            return
        if self.leaf is not None:
            yield self.leaf
        else:
            yield from self.left.iterIntersections(targetBounds)
            yield from self.right.iterIntersections(targetBounds)
