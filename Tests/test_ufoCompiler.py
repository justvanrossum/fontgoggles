from fontTools.ufoLib import UFOReader
from fontgoggles.misc.ufoCompiler import fetchCharacterMappingAndAnchors
from testSupport import getFontPath


def test_ufoCharacterMapping():
    ufoPath = getFontPath("MutatorSansBoldWideMutated.ufo")
    reader = UFOReader(ufoPath)
    cmap, revCmap, anchors = fetchCharacterMappingAndAnchors(reader.getGlyphSet(), ufoPath)
    assert cmap[0x0041] == "A"
    assert revCmap["A"] == [0x0041]
    # MutatorSansBoldWideMutated.ufo/glyphs/A_.glif contains a commented-out <unicode>
    # tag, that must not be parsed, as well as a commented-out <anchor>.
    assert 0x1234 not in cmap
    assert anchors == {"A": [("top", 645, 815)], "E": [("top", 582.5, 815)], "macroncmb": [("_top", 0, 815)]}
