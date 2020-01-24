from fontTools.ufoLib import UFOReader
from fontgoggles.font.dsFont import PointCollector
from testSupport import getFontPath


def test_pointCollector():
    ufoPath = getFontPath("MutatorSansBoldWideMutated.ufo")
    reader = UFOReader(ufoPath)
    glyphSet = reader.getGlyphSet()
    pen = PointCollector(glyphSet)
    glyphSet["B"].draw(pen)
    assert len(pen.points) == 38
    assert len(pen.tags) == 38
    assert pen.contours == [3, 37]
    assert pen.tags[:12] == [1, 1, 1, 1, 1, 1, 2, 2, 1, 2, 2, 1]

    pen = PointCollector(glyphSet)
    glyphSet["Aacute"].draw(pen)
    assert len(pen.points) == 20
    assert pen.contours == [3, 7, 11, 15, 19]

    pen = PointCollector(glyphSet)
    glyphSet["O"].draw(pen)
    assert len(pen.points) == 28
    assert pen.contours == [13, 27]


def test_pointCollectorQuad():
    ufoPath = getFontPath("QuadTest-Regular.ufo")
    reader = UFOReader(ufoPath)
    glyphSet = reader.getGlyphSet()
    pen = PointCollector(glyphSet)
    glyphSet["a"].draw(pen)
    assert len(pen.points) == 4
    assert len(pen.tags) == 4
    assert pen.contours == [3]
    assert pen.tags == [0, 0, 0, 0]
