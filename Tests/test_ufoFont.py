from fontTools.ufoLib import UFOReader
from fontgoggles.font.ufoFont import fetchCharacterMappingAndAnchors
from testSupport import getFontPath


def test_ufoCharacterMapping():
    ufoPath = getFontPath("MutatorSansBoldWide.ufo")
    reader = UFOReader(ufoPath)
    cmap, revCmap, anchors = fetchCharacterMappingAndAnchors(reader.getGlyphSet(), ufoPath)
    assert cmap[0x0041] == "A"
    assert revCmap["A"] == [0x0041]
    # MutatorSansBoldWide.ufo/glyphs/A_.glif contains a commented-out <unicode>
    # tag, that must not be parsed, as well as a commented-out <anchor>.
    assert 0x1234 not in cmap
    assert anchors == {"A": [("top", 645, 840)], "E": [("top", 582.5, 841)]}
