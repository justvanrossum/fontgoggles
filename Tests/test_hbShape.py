import pathlib
import pytest
from fontgoggles.misc.hbShape import Shaper


testRoot = pathlib.Path(__file__).resolve().parent


def getFontPath(fileName):
    return testRoot / "data" / fileName


ibmPlexTestStrings = [
    # test string, features, expected glyphs
    ("Type",     dict(),           ["T", "y", "p", "e"]),
    (["aring"],  dict(),           ["aring"]),  # glyph name input
    ([ord("å")], dict(),           ["aring"]),  # unicode code points input
    ("fierce",   dict(),           ["fi", "e", "r", "c", "e"]),
    ("fierce",   dict(liga=False), ["f", "i", "e", "r", "c", "e"]),
    ("12/34",    dict(),           ["one", "two", "slash", "three", "four"]),
    ("12/34",    dict(frac=True),  ['onesuperior', 'twosuperior', 'fraction', 'uni2083', 'uni2084']),
]

@pytest.mark.parametrize("testString,features,expectedGlyphNames", ibmPlexTestStrings)
def test_shape_latin(testString, features, expectedGlyphNames):
    s = Shaper.fromPath(getFontPath("IBMPlexSans-Regular.ttf"))
    glyphs = s.shape(testString, features=features)
    assert [g.name for g in glyphs] == expectedGlyphNames
