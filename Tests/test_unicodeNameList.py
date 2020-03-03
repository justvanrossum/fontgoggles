import pytest
from fontgoggles.misc.unicodeNameList import findPrefix


testData = [
    ("ROOTS", []),
    ("ROOT", [1542, 1543, 8730, 8731, 8732]),
    ("ROO", 22),
    ("RO", 407),
    ("R", 3386),
    ("", 131808),
]


@pytest.mark.parametrize("prefix,expectedChars", testData)
def test_findPrefix(prefix, expectedChars):
    chars = findPrefix(prefix)
    if isinstance(expectedChars, int):
        assert len(chars) == expectedChars
    else:
        assert chars == expectedChars
    assert sorted(chars) == chars
