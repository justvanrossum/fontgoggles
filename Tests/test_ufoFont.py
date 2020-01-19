from fontTools.ufoLib import UFOReader
from fontgoggles.font.ufoFont import _getCharacterMapping
from testSupport import getFontPath


def test_ufoCharacterMapping():
    ufoPath = getFontPath("MutatorSansBoldWide.ufo")
    reader = UFOReader(ufoPath)
    cmap = _getCharacterMapping(ufoPath, reader.getGlyphSet())
    assert cmap[0x0041] == "A"
    # MutatorSansBoldWide.ufo/glyphs/A_.glif contains a commented out <unicode>
    # tag, that must not be parsed.
    assert 0x1234 not in cmap
