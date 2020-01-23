from fontTools.ufoLib import UFOReader
from fontgoggles.font.dsFont import PointCollector
from testSupport import getFontPath


def test_pointCollector():
    ufoPath = getFontPath("MutatorSansBoldWideMutated.ufo")
    reader = UFOReader(ufoPath)
    glyphSet = reader.getGlyphSet()
    pen = PointCollector(glyphSet)
    glyphSet["B"].draw(pen)
    points = pen.getPointsArray()
    assert len(points) == 38
    assert len(pen.getTagsArray()) == 38
    assert list(pen.getContoursArray()) == [3, 37]
    assert list(pen.getTagsArray())[:12] == [1, 1, 1, 1, 1, 1, 2, 2, 1, 2, 2, 1]

    pen = PointCollector(glyphSet)
    glyphSet["Aacute"].draw(pen)
    points = pen.getPointsArray()
    assert len(points) == 20
    assert list(pen.getContoursArray()) == [3, 7, 11, 15, 19]

    pen = PointCollector(glyphSet)
    glyphSet["O"].draw(pen)
    points = pen.getPointsArray()
    assert len(points) == 28
    assert list(pen.getContoursArray()) == [13, 27]


def test_pointCollectorQuad():
    ufoPath = getFontPath("QuadTest-Regular.ufo")
    reader = UFOReader(ufoPath)
    glyphSet = reader.getGlyphSet()
    pen = PointCollector(glyphSet)
    glyphSet["a"].draw(pen)
    points = pen.getPointsArray()
    assert len(points) == 4
    assert len(pen.getTagsArray()) == 4
    assert list(pen.getContoursArray()) == [3]
    assert list(pen.getTagsArray()) == [0, 0, 0, 0]
