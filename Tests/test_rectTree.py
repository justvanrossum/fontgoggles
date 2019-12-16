import pytest
from fontgoggles.misc.rectTree import hasIntersection, RectTree


referenceRect = (100, 100, 200, 200)

testValues = [
    (0, 0, False),
    (0, 50, False),
    (0, 100, False),
    (0, 150, True),
    (0, 200, True),
    (0, 250, True),
    (100, 100, False),
    (100, 150, True),
    (100, 200, True),
    (100, 250, True),
    (150, 150, True),
    (150, 200, True),
    (150, 250, True),
    (200, 200, False),
    (200, 250, False),
    (250, 250, False),
    (250, 300, False),
]

testRects = [((xMin, yMin, xMax, yMax), xSects and ySects)
             for xMin, xMax, xSects in testValues
             for yMin, yMax, ySects in testValues]


@pytest.mark.parametrize("testRect,expectedTruth", testRects)
def test_hasIntersection(testRect, expectedTruth):
    assert hasIntersection(testRect, referenceRect) == expectedTruth
    assert hasIntersection(referenceRect, testRect) == expectedTruth


testBoundsSequence = [
    (0, 0, 100, 100),
    (50, 10, 150, 150),
    (130, -10, 200, 120),
    (210, 0, 300, 100),
]

testTargets = [
    ((10, -20, 20, -10), []),
    ((10, 10, 10, 10), [0]),
    ((10, 10, 20, 20), [0]),
    ((80, 10, 90, 20), [0, 1]),
    ((110, 10, 120, 20), [1]),
    ((170, 10, 180, 20), [2]),
    ((250, 10, 260, 20), [3]),
    ((0, 10, 320, 20), [0, 1, 2, 3]),
]


@pytest.mark.parametrize("targetRect,expectedIndices", testTargets)
def test_rectTree_intersections(targetRect, expectedIndices):
    tree = RectTree.fromSeq([(b, i) for i, b in enumerate(testBoundsSequence)])
    assert list(tree.iterIntersections(targetRect)) == expectedIndices
    if expectedIndices:
        assert tree.firstIntersection(targetRect) == expectedIndices[0]
    else:
        assert tree.firstIntersection(targetRect) is None


def test_empty_rectTree():
    tree = RectTree.fromSeq([])
    assert list(tree.iterIntersections((0, 0, 1000, 1000))) == []
    assert tree.firstIntersection((0, 0, 1000, 1000)) is None
