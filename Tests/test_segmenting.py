from collections import deque
import pytest
from fontgoggles.misc.segmenting import getBiDiInfo, detectScript, textSegments


testData = [
    ("Abc",
     {'base_dir': 'L',
      'base_level': 0,
      'chars': [{'ch': 'A',
                 'index': 0,
                 'level': 0,
                 'orig': 'L',
                 'type': 'L'},
                {'ch': 'b',
                 'index': 1,
                 'level': 0,
                 'orig': 'L',
                 'type': 'L'},
                {'ch': 'c',
                 'index': 2,
                 'level': 0,
                 'orig': 'L',
                 'type': 'L'}],
      'runs': deque([{'eor': 'L',
                      'length': 3,
                      'sor': 'L',
                      'start': 0,
                      'type': 'L'}])}),
    ("\u062D\u062A\u0649",
     {'base_dir': 'R',
      'base_level': 1,
      'chars': [{'ch': '\u0649',
                 'index': 2,
                 'level': 1,
                 'orig': 'AL',
                 'type': 'R'},
                {'ch': '\u062A',
                 'index': 1,
                 'level': 1,
                 'orig': 'AL',
                 'type': 'R'},
                {'ch': '\u062D',
                 'index': 0,
                 'level': 1,
                 'orig': 'AL',
                 'type': 'R'}],
      'runs': deque([{'eor': 'R',
                      'length': 3,
                      'sor': 'R',
                      'start': 0,
                      'type': 'AL'}])}),
    ("\u062D\u062A\u064912",
     {'base_dir': 'R',
      'base_level': 1,
      'chars': [{'ch': '1',
                 'index': 3,
                 'level': 2,
                 'orig': 'EN',
                 'type': 'AN'},
                {'ch': '2',
                 'index': 4,
                 'level': 2,
                 'orig': 'EN',
                 'type': 'AN'},
                {'ch': '\u0649',
                 'index': 2,
                 'level': 1,
                 'orig': 'AL',
                 'type': 'R'},
                {'ch': '\u062A',
                 'index': 1,
                 'level': 1,
                 'orig': 'AL',
                 'type': 'R'},
                {'ch': '\u062D',
                 'index': 0,
                 'level': 1,
                 'orig': 'AL',
                 'type': 'R'}],
      'runs': deque([{'eor': 'R',
                      'length': 5,
                      'sor': 'R',
                      'start': 0,
                      'type': 'EN'}])}),
    ("\u0627\u064f\u0633",
     {'base_dir': 'R',
      'base_level': 1,
      'chars': [{'ch': 'س',
                 'index': 2,
                 'level': 1,
                 'orig': 'AL',
                 'type': 'R'},
                {'ch': 'ُ',
                 'index': 1,
                 'level': 1,
                 'orig': 'NSM',
                 'type': 'R'},
                {'ch': 'ا',
                 'index': 0,
                 'level': 1,
                 'orig': 'AL',
                 'type': 'R'}],
      'runs': deque([{'eor': 'R',
                      'length': 3,
                      'sor': 'R',
                      'start': 0,
                      'type': 'AL'}])}),
    (
        "\u0639\u05b7\u0631\u05b7\u0628\u05b4",
        {
            "base_dir": "R",
            "base_level": 1,
            "chars": [
                {"ch": "ִ", "index": 5, "level": 1, "orig": "NSM", "type": "R"},
                {"ch": "ب", "index": 4, "level": 1, "orig": "AL", "type": "R"},
                {"ch": "ַ", "index": 3, "level": 1, "orig": "NSM", "type": "R"},
                {"ch": "ر", "index": 2, "level": 1, "orig": "AL", "type": "R"},
                {"ch": "ַ", "index": 1, "level": 1, "orig": "NSM", "type": "R"},
                {"ch": "ع", "index": 0, "level": 1, "orig": "AL", "type": "R"},
            ],
            "runs": deque(
                [{"eor": "R", "length": 6, "sor": "R", "start": 0, "type": "NSM"}]
            ),
        },
    ),
]


@pytest.mark.parametrize("testString,expectedInfo", testData)
def test_getBiDiInfo_ltr(testString, expectedInfo):
    info = getBiDiInfo(testString)
    assert info == expectedInfo


testDataDetectScript = [
    (" ", ['Zxxx']),
    ("abc", ['Latn', 'Latn', 'Latn']),
    ("(abc)", ['Latn', 'Latn', 'Latn', 'Latn', 'Latn']),
    ("\u0627\u064f\u0633", ['Arab', 'Arab', 'Arab']),
    ("(\u0627\u064f\u0633)", ['Arab', 'Arab', 'Arab', 'Arab', 'Arab']),
    ("a(\u0627\u064f\u0633)", ['Latn', 'Latn', 'Arab', 'Arab', 'Arab', 'Arab']),
    ("a(\u0627\u064f\u0633)a", ['Latn', 'Latn', 'Arab', 'Arab', 'Arab', 'Latn', 'Latn']),
    ("\u0627\u064f(a)\u0633", ['Arab', 'Arab', 'Arab', 'Latn', 'Arab', 'Arab']),
]


@pytest.mark.parametrize("testString,expectedScripts", testDataDetectScript)
def test_detectScript(testString, expectedScripts):
    assert detectScript(testString) == expectedScripts


testDataTextSegments = [
    ("a", 0, [("a", "Latn", 0, 0)]),
    ("\u1FF0", 0, [("\u1FF0", "Zzzz", 0, 0)]),  # test char should *not* be defined in Unicode: issue #313
    ("\u0627", 1, [("\u0627", "Arab", 1, 0)]),
    ("a\u0627", 0, [("a", "Latn", 0, 0), ("\u0627", "Arab", 1, 1)]),
    ("\u0627123", 1, [("\u0627", "Arab", 1, 0), ("123", "Arab", 2, 1)]),
    ("\u0627123\u0627", 1, [("\u0627", "Arab", 1, 0), ("123", "Arab", 2, 1), ("\u0627", "Arab", 1, 4)]),
    ("123\u0627", 1, [("123", "Arab", 2, 0), ("\u0627", "Arab", 1, 3)]),
    ("a123\u0627", 0, [("a123", "Latn", 0, 0), ("\u0627", "Arab", 1, 4)]),
    ("すペ", 0, [("すペ", "Hira", 0, 0)]),  # Kana is folded to Hira, see issue #310
    ("ペす", 0, [("ペす", "Kana", 0, 0)]),  # Hira is folded to Kana, see issue #310
]


@pytest.mark.parametrize("testString,expectedBaseLevel,expectedSegments", testDataTextSegments)
def test_textSegments(testString, expectedBaseLevel, expectedSegments):
    segments, baseLevel = textSegments(testString)
    assert baseLevel == expectedBaseLevel
    assert len(segments) == len(expectedSegments)
    for segment, expectedSegment in zip(segments, expectedSegments):
        assert segment == expectedSegment
