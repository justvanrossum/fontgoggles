import pytest
from fontgoggles.misc.textInfo import TextInfo


testData = [
    ("abc", True, None, "abc", [3], "LTR", "left"),
    ("\u062D\u062A\u064912", True, None, "12\u0649\u062A\u062D", [2, 3], "LTR", "right"),
    ("\u062D\u062A\u064912", False, None, "\u062D\u062A\u064912", [2, 3], None, "right"),
    ("abc", True, "RTL", "abc", [3], "RTL", "right"),
]

@pytest.mark.parametrize("org,bidi,dirOverride,result,runLengths,dir,align", testData)
def test_textInfo(org, bidi, dirOverride, result, runLengths, dir, align):
    ti = TextInfo(org)
    ti.shouldApplyBiDi = bidi
    ti.directionOverride = dirOverride
    assert ti.text == result
    assert ti.directionForShaper == dir
