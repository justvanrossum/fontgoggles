import pathlib
import pytest
from fontgoggles.font import getOpener, sniffFontType, sortedFontPathsAndNumbers
from fontgoggles.misc.textInfo import TextInfo
from testSupport import getFontPath, testDataFolder


def test_sniffFontType():
    fontPath = getFontPath("IBMPlexSans-Regular.ttf")
    assert sniffFontType(fontPath) == "ttf"


openFontsTestData = [
    ("Amiri-Regular.ttf",
        {'familyName': 'Amiri',
         'italicAngle': -0.0,
         'styleName': 'Regular',
         'suffix': 'ttf',
         'weight': 400,
         'width': 5},
        ['calt', 'ccmp', 'curs', 'dnom', 'fina', 'init',
         'kern', 'liga', 'mark', 'medi', 'mkmk', 'numr',
         'pnum', 'rlig', 'rtlm', 'ss01', 'ss02', 'ss03',
         'ss04', 'ss05', 'ss06', 'ss07', 'ss08'],
        {'DFLT': set(), 'arab': {'ARA ', 'KSH ', 'MLY ', 'SND ', 'URD '}, 'latn': {'TRK '}},
        [],
        "فعل", ['uni0644.fina', 'uni0639.medi', 'uni0641.init']),
    ("IBMPlexSans-Regular.ttf",
        {'familyName': 'IBM Plex Sans',
         'italicAngle': 0.0,
         'styleName': 'Regular',
         'suffix': 'ttf',
         'weight': 400,
         'width': 5},
        ['aalt', 'ccmp', 'dnom', 'frac', 'kern', 'liga',
         'mark', 'numr', 'ordn', 'salt', 'sinf', 'ss01',
         'ss02', 'ss03', 'ss04', 'ss05', 'subs', 'sups',
         'zero',
         ],
        {'DFLT': set(), 'cyrl': set(), 'grek': set(), 'latn': set()},
        [],
        "Kofi", ["K", "o", "fi"]),
    ("MutatorSans.ttf",
        {'familyName': 'MutatorMathTest',
         'italicAngle': 0.0,
         'styleName': 'LightCondensed',
         'suffix': 'ttf',
         'weight': 400,
         'width': 5},
        ['kern', 'rvrn'],
        {'DFLT': set()},
        [{'defaultValue': 0.0,
          'maxValue': 1000.0,
          'minValue': 0.0,
          'name': 'Width',
          'tag': 'wdth'},
         {'defaultValue': 0.0,
          'maxValue': 1000.0,
          'minValue': 0.0,
          'name': 'Weight',
          'tag': 'wght'}],
        "HI", ["H", "I.narrow"]),
    ("NotoNastaliqUrdu-Regular.ttf",
        {'familyName': 'Noto Nastaliq Urdu',
         'italicAngle': 0.0,
         'styleName': 'Regular',
         'suffix': 'ttf',
         'weight': 400,
         'width': 5},
        ['ccmp', 'curs', 'fina', 'init', 'isol', 'mark', 'medi', 'mkmk', 'rlig'],
        {'DFLT': set(), 'arab': {'ARA ', 'FAR ', 'KSH ', 'SND ', 'URD '}, 'latn': set()},
        [],
        "فعل", ['LamFin', 'AinMed.inT3outT1', 'OneDotAboveNS', 'sp0', 'FehxIni.outT3']),
    ("MutatorSansBoldWide.ufo",
        {'familyName': 'MutatorMathTest',
         'italicAngle': 0,
         'styleName': 'BoldWide',
         'suffix': 'ufo'},
        ['calt', 'ss01'],
        {'DFLT': set()},
        [],
        "HIiIII", ["H", "I", ".notdef", "I", "I.narrow", "I"])
]

@pytest.mark.parametrize("fileName,expectedSortInfo,features,scripts,axes,text,glyphNames",
                         openFontsTestData)
@pytest.mark.asyncio
async def test_openFonts(fileName,
                         expectedSortInfo,
                         features,
                         scripts,
                         axes,
                         text,
                         glyphNames):
    fontPath = getFontPath(fileName)
    numFonts, opener, getSortInfo = getOpener(fontPath)
    assert numFonts(fontPath) == 1
    font, fontData = await opener(fontPath, 0)
    sortInfo = getSortInfo(fontPath, 0)
    assert sortInfo == expectedSortInfo
    assert font.features == features
    assert font.scripts == scripts
    assert font.axes == axes
    run = font.getGlyphRun(text)
    assert [gi.name for gi in run] == glyphNames


def test_iterFontPathsAndNumbers():
    results = []
    paths = [
      testDataFolder / "Amiri",
      testDataFolder / "IBM-Plex",
      testDataFolder / "MutatorSans",
      testDataFolder / "Noto",
      testDataFolder / "FontGoggles",
    ]
    for fontPath, fontNumber, in sortedFontPathsAndNumbers(paths, ("suffix", "familyName",)):
        results.append((fontPath.name, fontNumber))
    # TODO: add .ttc test font
    expectedResults = [
        ('IBMPlexSans-Regular.otf', 0),
        ('Amiri-Regular.ttf', 0),
        ('IBMPlexSans-Regular.ttf', 0),
        ('IBMPlexSansArabic-Regular.ttf', 0),
        ('MutatorSans.ttf', 0),
        ('NotoNastaliqUrdu-Regular.ttf', 0),
        ('QuadTest-Regular.ttf', 0),
        ('MutatorSansBoldWide.ufo', 0),
    ]
    assert expectedResults == results


@pytest.mark.asyncio
async def test_getGlyphRunFromTextInfo():
    fontPath = getFontPath('IBMPlexSansArabic-Regular.ttf')
    numFonts, opener, getSortInfo = getOpener(fontPath)
    font, fontData = await opener(fontPath, 0)
    textInfo = TextInfo("abc")
    glyphs, endPos = font.getGlyphRunFromTextInfo(textInfo)
    assert [g.pos for g in glyphs] == [(0, 0), (534, 0), (1114, 0)]
