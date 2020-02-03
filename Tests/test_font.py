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
        {'calt', 'ccmp', 'dnom', 'fina', 'init',
         'liga', 'medi', 'numr',
         'pnum', 'rlig', 'rtlm', 'ss01', 'ss02', 'ss03',
         'ss04', 'ss05', 'ss06', 'ss07', 'ss08'},
        {'curs', 'kern','mark', 'mkmk', 'ss05'},
        {'DFLT': set(), 'arab': {'ARA ', 'KSH ', 'MLY ', 'SND ', 'URD '}, 'latn': {'TRK '}},
        {},
        [],
        "فعل", ['uni0644.fina', 'uni0639.medi', 'uni0641.init']),
    ("IBMPlexSans-Regular.ttf",
        {'familyName': 'IBM Plex Sans',
         'italicAngle': 0.0,
         'styleName': 'Regular',
         'suffix': 'ttf',
         'weight': 400,
         'width': 5},
        {'aalt', 'ccmp', 'dnom', 'frac', 'liga', 'numr', 'ordn',
         'salt', 'sinf', 'ss01', 'ss02', 'ss03', 'ss04', 'ss05',
         'subs', 'sups', 'zero'},
        {'kern', 'mark'},
        {'DFLT': set(), 'cyrl': set(), 'grek': set(), 'latn': set()},
        {},
        [],
        "Kofi", ["K", "o", "fi"]),
    ("IBMPlexSans-Regular.ttx",
        {},
        {'aalt', 'ccmp', 'dnom', 'frac', 'liga', 'numr', 'ordn',
         'salt', 'sinf', 'ss01', 'ss02', 'ss03', 'ss04', 'ss05',
         'subs', 'sups', 'zero'},
        {'kern', 'mark'},
        {'DFLT': set(), 'cyrl': set(), 'grek': set(), 'latn': set()},
        {},
        [],
        "Kofi", ["K", "o", "fi"]),
    ("MutatorSans.ttf",
        {'familyName': 'MutatorMathTest',
         'italicAngle': 0.0,
         'styleName': 'LightCondensed',
         'suffix': 'ttf',
         'weight': 1,
         'width': 1},
        {'rvrn'},
        {'kern'},
        {'DFLT': set()},
        {'wdth': {'defaultValue': 0.0,
                  'maxValue': 1000.0,
                  'minValue': 0.0,
                  'name': 'Width'},
         'wght': {'defaultValue': 0.0,
                  'maxValue': 1000.0,
                  'minValue': 0.0,
                  'name': 'Weight'}},
        [],
        "HI", ["H", "I.narrow"]),
    ("NotoNastaliqUrdu-Regular.ttf",
        {'familyName': 'Noto Nastaliq Urdu',
         'italicAngle': 0.0,
         'styleName': 'Regular',
         'suffix': 'ttf',
         'weight': 400,
         'width': 5},
        {'init', 'rlig', 'fina', 'isol', 'ccmp', 'medi'},
        {'curs', 'mkmk', 'mark'},
        {'DFLT': set(), 'arab': {'ARA ', 'FAR ', 'KSH ', 'SND ', 'URD '}, 'latn': set()},
        {},
        [],
        "فعل", ['LamFin', 'AinMed.inT3outT1', 'OneDotAboveNS', 'sp0', 'FehxIni.outT3']),
    ("MutatorSansBoldWideMutated.ufo",
        {'familyName': 'MutatorMathTest',
         'italicAngle': 0,
         'styleName': 'BoldWide',
         'suffix': 'ufo'},
        {'calt', 'ss01'},
        {'kern', 'mark'},
        {'DFLT': set()},
        {},
        ['features_test.fea'],
        "HIiIII\u0100A\u0304", ["H", "I", ".notdef", "I", "I.narrow", "I", "A", "macroncmb", "A", "macroncmb"]), 
    ('MutatorSans.designspace',
        {},
        {'rvrn'},
        {'kern'},
        {'DFLT': set()},
        {'wdth': {'defaultValue': 0.0,
                  'maxValue': 1000.0,
                  'minValue': 0.0,
                  'name': 'Width'},
         'wght': {'defaultValue': 0.0,
                  'maxValue': 1000.0,
                  'minValue': 0.0,
                  'name': 'Weight'}},
        ['MutatorSansLightCondensed.ufo',
         'MutatorSansBoldCondensed.ufo',
         'MutatorSansLightWide.ufo',
         'MutatorSansBoldWide.ufo',
         'MutatorSansLightCondensed.ufo',
         'MutatorSansLightCondensed.ufo',
         'MutatorSansLightCondensed.ufo'],
        "A", ["A"]),
]

@pytest.mark.parametrize("fileName,expectedSortInfo,featuresGSUB,featuresGPOS,scripts,axes,ext,text,glyphNames",
                         openFontsTestData)
@pytest.mark.asyncio
async def test_openFonts(fileName,
                         expectedSortInfo,
                         featuresGSUB,
                         featuresGPOS,
                         scripts,
                         axes,
                         ext,
                         text,
                         glyphNames):
    fontPath = getFontPath(fileName)
    numFonts, opener, getSortInfo = getOpener(fontPath)
    assert numFonts(fontPath) == 1
    font, fontData = await opener(fontPath, 0)
    sortInfo = getSortInfo(fontPath, 0)
    assert sortInfo == expectedSortInfo
    assert font.featuresGSUB == featuresGSUB
    assert font.featuresGPOS == featuresGPOS
    assert font.scripts == scripts
    assert font.axes == axes
    run = font.getGlyphRun(text)
    assert [gi.name for gi in run] == glyphNames
    assert ext == [p.name for p in font.getExternalFiles()]


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
        ('IBMPlexSans-Regular.ttx', 0),
        ('MutatorSans.designspace', 0),
        ('IBMPlexSans-Regular.otf', 0),
        ('Amiri-Regular.ttf', 0),
        ('IBMPlexSans-Regular.ttf', 0),
        ('IBMPlexSansArabic-Regular.ttf', 0),
        ('MutatorSans.ttf', 0),
        ('NotoNastaliqUrdu-Regular.ttf', 0),
        ('QuadTest-Regular.ttf', 0),
        ('MutatorSansIntermediateCondensed.ufo', 0),
        ('MutatorSansIntermediateWide.ufo', 0),
        ('MutatorSansBoldCondensed.ufo', 0),
        ('MutatorSansBoldWide.ufo', 0),
        ('MutatorSansBoldWideMutated.ufo', 0),
        ('MutatorSansLightCondensed.ufo', 0),
        ('MutatorSansLightCondensed_support.S.middle.ufo', 0),
        ('MutatorSansLightCondensed_support.S.wide.ufo', 0),
        ('MutatorSansLightCondensed_support.crossbar.ufo', 0),
        ('MutatorSansLightWide.ufo', 0),
        ('QuadTest-Regular.ufo', 0),
    ]
    assert expectedResults == results


testDataGetGlyphRun = [
    ("fit", ["fi", "t"],
     [(0, 0), (567, 0)]),
    ("\u062D\u062A\u0649", ['uniFC74', 'uniFEA3'],
     [(0, 0), (890, 0)]),
]


@pytest.mark.parametrize("text,expectedGlyphNames,expectedPositions", testDataGetGlyphRun)
@pytest.mark.asyncio
async def test_getGlyphRunFromTextInfo(text, expectedGlyphNames, expectedPositions):
    fontPath = getFontPath('IBMPlexSansArabic-Regular.ttf')
    numFonts, opener, getSortInfo = getOpener(fontPath)
    font, fontData = await opener(fontPath, 0)
    textInfo = TextInfo(text)
    glyphs = font.getGlyphRunFromTextInfo(textInfo)
    glyphNames = [g.name for g in glyphs]
    positions = [g.pos for g in glyphs]
    assert expectedGlyphNames == glyphNames
    assert expectedPositions == positions


@pytest.mark.skip(reason="needs unreleased uharfbuzz PR #26")
@pytest.mark.asyncio
async def test_verticalGlyphMetricsFromUFO():
    fontPath = getFontPath('MutatorSansBoldWideMutated.ufo')
    numFonts, opener, getSortInfo = getOpener(fontPath)
    font, fontData = await opener(fontPath, 0)
    textInfo = TextInfo("ABCDE")
    textInfo.directionOverride = "TTB"
    glyphs = font.getGlyphRunFromTextInfo(textInfo)
    glyphNames = [g.name for g in glyphs]
    ax = [g.ax for g in glyphs]
    ay = [g.ay for g in glyphs]
    dx = [g.dx for g in glyphs]
    dy = [g.dy for g in glyphs]
    expectedAX = [0, 0, 0, 0, 0]
    expectedAY = [-1022, -1000, -1000, -1000, -1000]
    expectedDX = [-645, -635, -687, -658, -560]
    expectedDY = [-822, -800, -800, -800, -800]
    assert expectedAX == ax
    assert expectedAY == ay
    assert expectedDX == dx
    assert expectedDY == dy
