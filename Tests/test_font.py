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
         'locl', 'liga', 'medi', 'numr',
         'pnum', 'rlig', 'rtlm', 'ss01', 'ss02', 'ss03',
         'ss04', 'ss05', 'ss06', 'ss07', 'ss08'},
        {'curs', 'kern', 'mark', 'mkmk', 'ss05'},
        {'DFLT': set(), 'arab': {'ARA ', 'KSH ', 'MLY ', 'SND ', 'URD '}, 'latn': {'TRK '}},
        {},
        [],
        {},
        "فعل", ['uni0644.fina', 'uni0639.medi', 'uni0641.init'], None, None),
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
        {},
        "Kofi", ["K", "o", "fi"], None, None),
    ("IBMPlexSansArabic-Regular.ttf",
        {'familyName': 'IBM Plex Sans Arabic',
         'italicAngle': 0.0,
         'styleName': 'Regular',
         'suffix': 'ttf',
         'weight': 400,
         'width': 5},
        {'aalt', 'calt', 'ccmp', 'dnom', 'fina', 'frac', 'init',
         'locl', 'liga', 'medi', 'numr', 'ordn', 'rlig', 'salt',
         'sinf', 'ss01', 'ss02', 'ss03', 'ss04', 'ss05', 'ss06',
         'subs', 'sups', 'zero'},
        {'kern', 'mark', 'mkmk'},
         {'DFLT': set(), 'arab': {'URD '}, 'latn': set()},
        {},
        [],
        {},
        "مَتْن‌وَنِوِشْتِه", ['uniFEEA',
                      'uni0650',
                      'uniFE98',
                      'uni0652',
                      'uniFEB7',
                      'uni0650',
                      'uniFEEE',
                      'uni0650',
                      'uniFEE7',
                      'uni064E',
                      'uni0648',
                      'space',
                      'uni0652',
                      'uniFC73',
                      'uni064E',
                      'uniFEE3'], None, None),
    ("IBMPlexSans-Regular.ttx",
        {},
        {'aalt', 'ccmp', 'dnom', 'frac', 'liga', 'numr', 'ordn',
         'salt', 'sinf', 'ss01', 'ss02', 'ss03', 'ss04', 'ss05',
         'subs', 'sups', 'zero'},
        {'kern', 'mark'},
        {'DFLT': set(), 'cyrl': set(), 'grek': set(), 'latn': set()},
        {},
        [],
        {},
        "Kofi", ["K", "o", "fi"], None, None),
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
                  'hidden': False,
                  'maxValue': 1000.0,
                  'minValue': 0.0,
                  'name': 'Width'},
         'wght': {'defaultValue': 0.0,
                  'hidden': False,
                  'maxValue': 1000.0,
                  'minValue': 0.0,
                  'name': 'Weight'}},
        [],
        {},
        "HI", ["H", "I.narrow"], None, None),
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
        {},
        "فعل", ['LamFin', 'AinMed.inT3outT1', 'OneDotAboveNS', 'sp0', 'FehxIni.outT3'], None, None),
    ("NotoSansMyanmar-Regular.ttf",
        {'familyName': 'Noto Sans Myanmar',
         'italicAngle': -0.0,
         'styleName': 'Regular',
         'suffix': 'ttf',
         'weight': 400,
         'width': 5},
        {'locl', 'blws', 'abvs', 'blwf'},
        {'kern', 'mark', 'mkmk'},
        {'mym2': {'KSW ', 'MON '}},
        {},
        [],
        {},
        "က္က", ['ka', 'ka.sub'], None, "mym2"),
    ("MutatorSansBoldWideMutated.ufo",
        {'familyName': 'MutatorMathTest',
         'italicAngle': 0,
         'styleName': 'BoldWide',
         'suffix': 'ufo'},
        {'calt', 'ss01'},
        {'kern', 'mark'},
        {'DFLT': set(), 'latn': set()},
        {},
        ['features_test.fea', 'features_test_nested.fea'],
        {},
        "HIiIII\u0100A\u0304", ["H", "I", ".notdef", "I", "I.narrow", "I", "A", "macroncmb", "A", "macroncmb"], None, None),
    ('MutatorSans.designspace',
        {},
        {'rvrn'},
        {'kern'},
        {'DFLT': set(), 'latn': set()},
        {'wdth': {'defaultValue': 0.0,
                  'hidden': False,
                  'maxValue': 1000.0,
                  'minValue': 0.0,
                  'name': 'Width'},
         'wght': {'defaultValue': 0.0,
                  'hidden': False,
                  'maxValue': 1000.0,
                  'minValue': 0.0,
                  'name': 'Weight'}},
        ['MutatorSansBoldCondensed.ufo',
         'MutatorSansBoldWide.ufo',
         'MutatorSansLightCondensed.ufo',
         'MutatorSansLightWide.ufo'],
        {},
        "A", ["A"], None, None),
    ('MutatorSansUFOZ.designspace',
        {},
        {'calt', 'ss01'},
        {'kern', 'mark'},
        {'DFLT': set(), 'latn': set()},
        {'wght': {'defaultValue': 0.0,
                  'hidden': False,
                  'maxValue': 1000.0,
                  'minValue': 0.0,
                  'name': 'Weight'}},
        ['MutatorSansBoldWideMutated.ufoz', 'features_test.fea', 'features_test_nested.fea'],
        {},
        "A", ["A"], None, None),
    ('MiniMutatorSans.designspace',
        {},
        set(),
        {'kern'},
        {'DFLT': set(), 'latn': set()},
        {'wdth': {'defaultValue': 100.0,
                  'hidden': False,
                  'maxValue': 700.0,
                  'minValue': 100.0,
                  'name': 'Width'}},
        ['MiniMutatorSansBoldCondensed.ufo',
         'MiniMutatorSansBoldWide.ufo'],
        {'wdth': 400},
        "TABC", ["T", "A", "B", "C"], [692, 850, 822, 932], None),
    ('MutatorSansBoldWideMutated.ufoz',
        {'familyName': 'MutatorMathTest', 'italicAngle': 0, 'styleName': 'BoldWide', 'suffix': 'ufoz'},
        {'calt', 'ss01'},
        {'kern', 'mark'},
        {'DFLT': set(), 'latn': set()},
        {},
        ['features_test.fea', 'features_test_nested.fea'],
        {},
        "A", ["A"], [1290], None),
]

@pytest.mark.parametrize("fileName,expectedSortInfo,featuresGSUB,featuresGPOS,scripts,axes,ext,location,text,glyphNames,ax,script",
                         openFontsTestData)
@pytest.mark.asyncio
async def test_openFonts(fileName,
                         expectedSortInfo,
                         featuresGSUB,
                         featuresGPOS,
                         scripts,
                         axes,
                         ext,
                         location,
                         text,
                         glyphNames,
                         ax,
                         script):
    fontPath = getFontPath(fileName)
    numFonts, opener, getSortInfo = getOpener(fontPath)
    assert numFonts(fontPath) == 1
    font = opener(fontPath, 0)
    await font.load(print)
    sortInfo = getSortInfo(fontPath, 0)
    assert sortInfo == expectedSortInfo
    assert font.featuresGSUB == featuresGSUB
    assert font.featuresGPOS == featuresGPOS
    assert font.scripts == scripts
    assert font.axes == axes
    run = font.getGlyphRun(text, varLocation=location, script=script)
    assert [gi.name for gi in run] == glyphNames
    assert ext == [p.name for p in font.getExternalFiles()]
    if ax is not None:
        assert [gi.ax for gi in run] == ax


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
    expectedResults = [
        ('IBMPlexSans-Regular.ttx', 0),
        ('MutatorSans.designspace', 0),
        ('MutatorSansDS5.designspace', 0),
        ('MutatorSansDS5.designspace', 1),
        ('MutatorSansUFOZ.designspace', 0),
        ('QuadTest-Regular.ttx', 0),
        ('IBMPlexSans-Regular.otf', 0),
        ('MutatorSans.ttc', 0),
        ('MutatorSans.ttc', 1),
        ('MutatorSans.ttc', 2),
        ('MutatorSans.ttc', 3),
        ('Amiri-Regular.ttf', 0),
        ('IBMPlexSans-Regular.ttf', 0),
        ('IBMPlexSansArabic-Regular.ttf', 0),
        ('MutatorSans.ttf', 0),
        ('NotoNastaliqUrdu-Regular.ttf', 0),
        ('NotoSansMyanmar-Regular.ttf', 0),
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
        ('MutatorSansBoldWideMutated.ufoz', 0),
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
    font = opener(fontPath, 0)
    await font.load(None)
    textInfo = TextInfo(text)
    glyphs = font.getGlyphRunFromTextInfo(textInfo)
    glyphNames = [g.name for g in glyphs]
    positions = [g.pos for g in glyphs]
    assert expectedGlyphNames == glyphNames
    assert expectedPositions == positions


@pytest.mark.asyncio
async def test_mapGlyphsToChars():
    text = "عربي بِّ"
    fontPath = getFontPath('Amiri-Regular.ttf')
    numFonts, opener, getSortInfo = getOpener(fontPath)
    font = opener(fontPath, 0)
    await font.load(None)
    textInfo = TextInfo(text)
    glyphs = font.getGlyphRunFromTextInfo(textInfo)
    charIndices = []
    for glyphIndex in range(len(glyphs)):
        charIndices.append(glyphs.mapGlyphsToChars({glyphIndex}))
    expectedCharIndices = [{7}, {6}, {5}, {4}, {3}, {2}, {1}, {0}]
    assert expectedCharIndices == charIndices
    glyphIndices = []
    for charIndex in range(len(text)):
        glyphIndices.append(glyphs.mapCharsToGlyphs({charIndex}))
    expectedGlyphIndices = [{7}, {6}, {5}, {4}, {3}, {2}, {1}, {0}]
    assert expectedGlyphIndices == glyphIndices


@pytest.mark.asyncio
async def test_verticalGlyphMetricsFromUFO():
    fontPath = getFontPath('MutatorSansBoldWideMutated.ufo')
    numFonts, opener, getSortInfo = getOpener(fontPath)
    font = opener(fontPath, 0)
    await font.load(None)
    textInfo = TextInfo("ABCDE")
    textInfo.directionOverride = "TTB"
    glyphs = font.getGlyphRunFromTextInfo(textInfo)
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
