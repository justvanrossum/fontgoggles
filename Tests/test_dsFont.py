import pytest
import sys
from fontTools.ufoLib import UFOReader
from fontgoggles.font.dsFont import DSFont, PointCollector
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

    pen = PointCollector(glyphSet, decompose=False)
    glyphSet["Aacute"].draw(pen)
    assert len(pen.points) == 0
    assert pen.contours == []
    assert pen.components == [("A", (1, 0, 0, 1, 0, 0)), ("acute", (1, 0, 0, 1, 484, 20))]

    pen = PointCollector(glyphSet, decompose=True)
    glyphSet["Aacute"].draw(pen)
    assert len(pen.points) == 20
    assert pen.contours == [3, 7, 11, 15, 19]
    assert pen.components == []

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


@pytest.mark.asyncio
async def test_DSFont():
    ufoPath = getFontPath("MutatorSans.designspace")
    font = DSFont(ufoPath, 0)
    await font.load(sys.stderr.write)
    expected = [
        'MutatorSansBoldCondensed.ufo',
        'MutatorSansBoldWide.ufo',
        'MutatorSansLightCondensed.ufo',
        'MutatorSansLightWide.ufo',
    ]
    assert expected == [p.name for p in font.getExternalFiles()]
    run = font.getGlyphRun("ABC")
    ax = [gi.ax for gi in run]
    assert [396, 443, 499] == ax
    # Glyph 'A' has custom vertical glyph metrics in the default master
    run = font.getGlyphRun("A", direction="TTB")
    assert run[0].ax == 0
    assert run[0].ay == -986
    assert run[0].dx == -198
    assert run[0].dy == -777
    # But not at the other masters, so expect defaults there
    run = font.getGlyphRun("A", varLocation=dict(wght=1000), direction="TTB")
    assert run[0].ax == 0
    assert run[0].ay == -900
    assert run[0].dx == -370
    assert run[0].dy == -700


@pytest.mark.asyncio
@pytest.mark.parametrize("ufoFileName, fontNumber, expectedBounds", [
    ("MutatorSans.designspace", 0, ((20, 0), (356, 700))),
    ("MutatorSansDS5.designspace", 0, ((20, 0), (356, 700))),
    ("MutatorSansDS5.designspace", 1, ((50, 0), (1090, 700))),
])
async def test_DSFont_getOutline(ufoFileName, fontNumber, expectedBounds):
    ufoPath = getFontPath(ufoFileName)
    font = DSFont(ufoPath, fontNumber)
    await font.load(sys.stderr.write)
    drawing, *_ = font.getGlyphDrawings(["A"])
    assert expectedBounds == drawing.path.bounds()
