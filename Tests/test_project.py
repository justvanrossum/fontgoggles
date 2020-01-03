import pytest
from fontgoggles.project import Project
from testSupport import getFontPath


@pytest.mark.asyncio
async def test_project_loadFonts():
    pr = Project()
    fontPath = getFontPath("IBMPlexSans-Regular.ttf")
    pr.addFont(fontPath, 0)
    font = pr.fonts.get((fontPath, 0))
    assert font is None
    await pr.loadFonts()
    font = pr.fonts[fontPath, 0]
    assert font.axes == {}  # simple check to see if we have a font at all
    with pytest.raises(KeyError):
        await pr.loadFont(fontPath, 1)


@pytest.mark.asyncio
async def test_project_loadFont():
    pr = Project()
    fontPath = getFontPath("IBMPlexSans-Regular.ttf")
    pr.addFont(fontPath, 0)
    await pr.loadFont(fontPath, 0)
    with pytest.raises(TypeError):
        pr.addFont("a string", 0)
    font = pr.fonts[fontPath, 0]
    assert font.axes == {}  # simple check to see if we have a font at all


def test_project_purgeFonts():
    pr = Project()
    fontPath1 = getFontPath("IBMPlexSans-Regular.ttf")
    pr.addFont(fontPath1, 0)
    fontPath2 = getFontPath("IBMPlexSans-Regular.otf")
    pr.addFont(fontPath2, 0)
    assert len(pr.fontItems) == 2
    assert list(pr.fonts) == [(fontPath1, 0), (fontPath2, 0)]
    item1 = dict(id="fontItem_0", fontKey=(fontPath1, 0))
    item2 = dict(id="fontItem_1", fontKey=(fontPath2, 0))
    assert pr.fontItems == [item1, item2]
    del pr.fontItems[0]
    assert list(pr.fonts) == [(fontPath1, 0), (fontPath2, 0)]
    pr.purgeFonts()
    assert list(pr.fonts) == [(fontPath2, 0)]
    del pr.fontItems[0]
    assert list(pr.fonts) == [(fontPath2, 0)]
    pr.purgeFonts()
    assert list(pr.fonts) == []
