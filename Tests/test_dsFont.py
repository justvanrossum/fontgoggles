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
    pen = PointCollector(glyphSet)
    glyphSet["Aacute"].draw(pen)
    points = pen.getPointsArray()
    assert len(points) == 20
