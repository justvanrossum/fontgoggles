from fontTools.ufoLib import UFOReader
from fontgoggles.font.ufoFont import fetchCharacterMappingAndAnchors
from testSupport import getFontPath


def test_ufoCharacterMapping():
    ufoPath = getFontPath("MutatorSansBoldWide.ufo")
    reader = UFOReader(ufoPath)
    cmap, anchors = fetchCharacterMappingAndAnchors(ufoPath, reader.getGlyphSet())
    assert cmap[0x0041] == "A"
    # MutatorSansBoldWide.ufo/glyphs/A_.glif contains a commented out <unicode>
    # tag, that must not be parsed.
    assert 0x1234 not in cmap
    assert anchors == {"A": [("top", 645, 840)], "E": [("top", 582.5, 841)]}
