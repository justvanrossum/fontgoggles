import pathlib
import pytest
from fontgoggles.font import iterFontNumbers
from fontgoggles.project import Project
from testSupport import getFontPath


@pytest.mark.asyncio
async def test_project_loadFonts():
    pr = Project()
    fontPath = getFontPath("IBMPlexSans-Regular.ttf")
    pr.addFont(fontPath, 0)
    fii = pr.fonts[0]
    assert fii.font is None
    await pr.loadFonts()
    fii = pr.fonts[0]
    assert fii.font.axes == {}  # simple check to see if we have a font at all


@pytest.mark.asyncio
async def test_project_loadFont():
    pr = Project()
    fontPath = getFontPath("IBMPlexSans-Regular.ttf")
    pr.addFont(fontPath, 0)
    await pr.fonts[0].load()
    with pytest.raises(TypeError):
        pr.addFont("a string", 0)
    fii = pr.fonts[0]
    assert fii.font.axes == {}  # simple check to see if we have a font at all


@pytest.mark.asyncio
async def test_project_purgeFonts():
    pr = Project()
    fontPath1 = getFontPath("IBMPlexSans-Regular.ttf")
    pr.addFont(fontPath1, 0)
    fontPath2 = getFontPath("IBMPlexSans-Regular.otf")
    pr.addFont(fontPath2, 0)
    assert len(pr.fonts) == 2
    assert [fii.fontKey for fii in pr.fonts] == [(fontPath1, 0), (fontPath2, 0)]
    assert [fii.identifier for fii in pr.fonts] == ["fontItem_0", "fontItem_1"]

    assert len(pr._fontLoader.fonts) == 0
    await pr.loadFonts()
    assert len(pr._fontLoader.fonts) == 2

    del pr.fonts[0]
    assert list(pr._fontLoader.fonts) == [(fontPath1, 0), (fontPath2, 0)]
    pr.purgeFonts()
    assert list(pr._fontLoader.fonts) == [(fontPath2, 0)]
    del pr.fonts[0]
    assert list(pr._fontLoader.fonts) == [(fontPath2, 0)]
    pr.purgeFonts()
    assert list(pr._fontLoader.fonts) == []


def test_project_dump_load(tmpdir):
    destPath = pathlib.Path(tmpdir / "test.gggls")
    pr = Project()
    fontPath1 = getFontPath("IBMPlexSans-Regular.ttf")
    pr.addFont(fontPath1, 0)
    fontPath2 = getFontPath("IBMPlexSans-Regular.otf")
    pr.addFont(fontPath2, 0)
    json = pr.asJSON(destPath.parent)
    pr2 = Project.fromJSON(json, destPath.parent)
    for f1, f2 in zip(pr.fonts, pr2.fonts):
        assert f1.fontKey == f2.fontKey


@pytest.mark.asyncio
async def test_project_load_ttc():
    pr = Project()
    fontPath = getFontPath("MutatorSans.ttc")
    for fontPath, fontNumber, getSortInfo in iterFontNumbers(fontPath):
        pr.addFont(fontPath, fontNumber)
    await pr.loadFonts()
