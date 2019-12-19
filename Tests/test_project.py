import pathlib
import pytest
from fontgoggles.project import Project
from testSupport import getFontPath


@pytest.mark.asyncio
async def test_project_loadFonts():
    pr = Project()
    fontPath = getFontPath("IBMPlexSans-Regular.ttf")
    pr.addFont(fontPath, 0)
    with pytest.raises(ValueError):
        font = pr.getFont(fontPath, 0)
    notLoadedMarker = object()
    font = pr.getFont(fontPath, 0, notLoadedMarker)
    assert font is notLoadedMarker
    await pr.loadFonts()
    font = pr.getFont(fontPath, 0)
    assert font.axes == []  # simple check to see if we have a font at all
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
    font = pr.getFont(fontPath, 0)
    assert font.axes == []  # simple check to see if we have a font at all
