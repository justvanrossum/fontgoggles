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
