import pytest
from fontgoggles.misc.unicodeNameList import findPrefix


testData = [
    ("ROOTS", []),
    ("ROOT", [1542, 1543, 8730, 8731, 8732, 129754]),
    ("ROO", 23),
    ("RO", 424),
    ("R", 3594),
    ("", 143668),
    ("YAMA", [3662, 3790]),
]


@pytest.mark.parametrize("prefix,expectedChars", testData)
def test_findPrefix(prefix, expectedChars):
    chars = findPrefix(prefix)
    if isinstance(expectedChars, int):
        assert len(chars) == expectedChars
    else:
        assert chars == expectedChars
    assert sorted(chars) == chars
