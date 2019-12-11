import pathlib
import pytest
from fontgoggles.font import openFonts, sniffFontType


testRoot = pathlib.Path(__file__).resolve().parent


def getFontPath(fileName):
    return testRoot / "data" / fileName


def test_sniffFontType():
    fontPath = getFontPath("IBMPlexSans-Regular.ttf")
    assert sniffFontType(fontPath) == "ttf"


@pytest.mark.asyncio
async def test_openFonts():
    fontPath = getFontPath("IBMPlexSans-Regular.ttf")
    features = [
        'aalt', 'ccmp', 'dnom', 'frac', 'liga', 'numr',
        'ordn', 'salt', 'sinf', 'ss01', 'ss02', 'ss03',
        'ss04', 'ss05', 'subs', 'sups', 'zero', 'kern',
        'mark',
    ]
    scripts = [
        'DFLT', 'cyrl', 'grek', 'latn', 'DFLT', 'cyrl',
        'grek', 'latn',
    ]
    languages = []
    async for font in openFonts(fontPath):
        assert font.features == features
        assert font.scripts == scripts
        assert font.languages == languages
        assert font.axes == []
        run = await font.getGlyphRun("Kofi")
        glyphNames = [gi.name for gi, outline in run]
        assert glyphNames == ["K", "o", "fi"]
