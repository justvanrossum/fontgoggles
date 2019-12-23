import pytest
from fontgoggles.misc.unicodeNameList import findPrefix


testData = [
    ("ROOTS", []),
    ("ROOT", [1542, 1543, 8730, 8731, 8732]),
    ("ROO", 12),
    ("RO", 352),
    ("R", 3312),
    ("", 131259),
]


@pytest.mark.parametrize("prefix,expectedChars", testData)
def test_findPrefix(prefix, expectedChars):
    chars = findPrefix(prefix)
    if isinstance(expectedChars, int):
        assert len(chars) == expectedChars
    else:
        assert chars == expectedChars
    assert sorted(chars) == chars
