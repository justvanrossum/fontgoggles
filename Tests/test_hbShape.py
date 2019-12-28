import pytest
from fontgoggles.misc.hbShape import HBShape, characterGlyphMapping, clusterMapping
from testSupport import getFontPath


ibmPlexTestStrings = [
    # test string, features, expected glyphs
    ("Type",     dict(),           ["T", "y", "p", "e"]),
    # (["aring"],  dict(),           ["aring"]),  # glyph name input
    ([ord("å")], dict(),           ["aring"]),  # unicode code points input
    ("fierce",   dict(),           ["fi", "e", "r", "c", "e"]),
    ("fierce",   dict(liga=False), ["f", "i", "e", "r", "c", "e"]),
    ("12/34",    dict(),           ["one", "two", "slash", "three", "four"]),
    ("12/34",    dict(frac=True),  ['onesuperior', 'twosuperior', 'fraction', 'uni2083', 'uni2084']),
]


@pytest.mark.parametrize("testString,features,expectedGlyphNames", ibmPlexTestStrings)
def test_shape_latin(testString, features, expectedGlyphNames):
    s = HBShape.fromPath(getFontPath("IBMPlexSans-Regular.ttf"))
    glyphs = s.shape(testString, features=features)
    assert [g.name for g in glyphs] == expectedGlyphNames


def test_shape_GlyphInfo_repr():
    s = HBShape.fromPath(getFontPath("IBMPlexSans-Regular.ttf"))
    glyphs = s.shape("a")
    assert repr(glyphs[0]) == "GlyphInfo(gid=4, name='a', cluster=0, dx=0, dy=0, ax=534, ay=0)"


clusterTestData = [
    ([0, 1, 2, 5, 6, 8], 10,
     [[0], [1], [2, 3, 4], [2, 3, 4], [2, 3, 4], [5], [6, 7], [6, 7], [8, 9], [8, 9]],
     [0, 1, 2, 2, 2, 5, 6, 6, 8, 8]),
    ([0, 1], 3,
     [[0], [1, 2], [1, 2]],
     [0, 1, 1]),
    ([], 0,
     [],
     []),
]


@pytest.mark.parametrize("clusters,numChars,expectedClusterToCharIndex,expectedCharIndexToCluster", clusterTestData)
def test_clusterMapping(clusters, numChars, expectedClusterToCharIndex, expectedCharIndexToCluster):
    clusterToCharIndex, charIndexToCluster = clusterMapping(clusters, numChars)
    assert clusterToCharIndex == expectedClusterToCharIndex
    assert charIndexToCluster == expectedCharIndexToCluster


clusterTestData2 = [
    ([0, 1, 2, 5, 6, 8], 10,
     [[0], [1], [2, 3, 4], [5], [6, 7], [8, 9]],
     [[0], [1], [2], [2], [2], [3], [4], [4], [5], [5]]),
    ([0, 1], 3,
     [[0], [1, 2]],
     [[0], [1], [1]]),
    ([0, 0, 1], 2,
     [[0], [0], [1]],
     [[0, 1], [2]]),
    ([0, 0, 1, 1], 2,
     [[0], [0], [1], [1]],
     [[0, 1], [2, 3]]),
    ([0, 0, 2, 2], 3,
     [[0, 1], [0, 1], [2], [2]],
     [[0, 1], [0, 1], [2, 3]]),
    ([], 0,
     [],
     []),
]

@pytest.mark.parametrize("clusters,numChars,expectedGlyphToChars,expectedCharToGlyphs", clusterTestData2)
def test_characterGlyphMapping(clusters, numChars, expectedGlyphToChars, expectedCharToGlyphs):
    glyphToChars, charToGlyphs = characterGlyphMapping(clusters, numChars)
    assert glyphToChars == expectedGlyphToChars
    assert charToGlyphs == expectedCharToGlyphs
