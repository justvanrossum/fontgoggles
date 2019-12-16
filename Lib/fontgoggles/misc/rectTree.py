from typing import Any, NamedTuple, Optional, Sequence, Tuple, Union
from fontTools.misc.arrayTools import unionRect


Number = Union[int, float]
Rectangle = Tuple[Number, Number, Number, Number]  # xMin, yMin, xMax, yMax


class RectTree(NamedTuple):

    """Given a sorted list of (rectangle, object) items, build a tree structure
    that allows to efficiently find objects that overlap with a target rectangle.

    Use the RectTree.fromSeq(seq) class method to build a tree.

    The tree.iterIntersections(targetRect) method iterates over the set of objects
    that overlap with targetRect (in order of the original sequence).

    The tree.firstIntersection(targetRect) method returns the first overlapping
    object or None.

    This implementation is targeted towards a more or less one-dimensional layout
    of the objects, for example a line of glyphs. The direction of the layout is
    not important, but it's most efficient to sort the objects along the intended
    direction. For example, a sequence of glyph bounding boxes that are layed out
    horizontally should be sorted horizontally (although right to left or left to
    right won't make a difference). The output of, say, hb-shape will do just
    fine, regardless of whether the layout is horizontal or vertical.

    Rectangles here have the form (xMin, yMin, xMax, yMax).
    """

    bounds: Rectangle
    leaf: Any
    left: Optional["RectTree"]
    right: Optional["RectTree"]

    @classmethod
    def fromSeq(cls, seq: Sequence[Tuple[Rectangle, Any]]):
        if len(seq) == 0:
            # empty tree, pass None for bounds as a special case
            return cls(None, None, None, None)
        elif len(seq) == 1:
            bounds, leaf = seq[0]
            return cls(bounds, leaf, None, None)
        mid = len(seq) // 2
        left = cls.fromSeq(seq[:mid])
        right = cls.fromSeq(seq[mid:])
        bounds = unionRect(left[0], right[0])
        return cls(bounds, None, left, right)

    def iterIntersections(self, targetBounds: Rectangle):
        if self.bounds is None:
            # empty tree
            return
        if not hasIntersection(self.bounds, targetBounds):
            return
        if self.left is None:
            assert self.right is None
            yield self.leaf
        else:
            yield from self.left.iterIntersections(targetBounds)
            yield from self.right.iterIntersections(targetBounds)

    def firstIntersection(self, targetBounds: Rectangle, default=None):
        return next(self.iterIntersections(targetBounds), default)


def hasIntersection(rect1, rect2):
    """Return a boolean. If the input rectangles intersect, return
    True, return False if the input rectangles do not intersect.
    """
    (xMin1, yMin1, xMax1, yMax1) = rect1
    (xMin2, yMin2, xMax2, yMax2) = rect2
    return ((xMin1 < xMax2 and xMax1 > xMin2) and (yMin1 < yMax2 and yMax1 > yMin2))
