import pathlib
import pytest
from fontgoggles.font import getOpener, sniffFontType


testRoot = pathlib.Path(__file__).resolve().parent


def getFontPath(fileName):
    return testRoot / "data" / fileName


def test_sniffFontType():
    fontPath = getFontPath("IBMPlexSans-Regular.ttf")
    assert sniffFontType(fontPath) == "ttf"


openFontsTestData = [
    ("IBMPlexSans-Regular.ttf",
        ['aalt', 'ccmp', 'dnom', 'frac', 'kern', 'liga',
         'mark', 'numr', 'ordn', 'salt', 'sinf', 'ss01',
         'ss02', 'ss03', 'ss04', 'ss05', 'subs', 'sups',
         'zero',
         ],
        ['DFLT', 'cyrl', 'grek', 'latn'],
        [],
        [],
        "Kofi", ["K", "o", "fi"]),
    ("MutatorSans.ttf",
        ['kern', 'rvrn'],
        ['DFLT'],
        [],
        [{'defaultValue': 0.0,
          'maxValue': 1000.0,
          'minValue': 0.0,
          'name': 'Width',
          'tag': 'wdth'},
         {'defaultValue': 0.0,
          'maxValue': 1000.0,
          'minValue': 0.0,
          'name': 'Weight',
          'tag': 'wght'},
        ],
        "HI", ["H", "I.narrow"]),
    ("NotoNastaliqUrdu-Regular.ttf",
        ['ccmp', 'curs', 'fina', 'init', 'isol', 'mark', 'medi', 'mkmk', 'rlig'],
        ['DFLT', 'arab', 'latn'],
        [],
        [],
        "فعل", ['LamFin', 'AinMed.inT3outT1', 'OneDotAboveNS', 'sp0', 'FehxIni.outT3']),
    ("MutatorSansBoldWide.ufo",
        [],
        [],
        [],
        [],
        "HIi", ["H", "I", ".notdef"])
]

@pytest.mark.parametrize("fileName,features,scripts,languages,axes,text,glyphNames",
                         openFontsTestData)
@pytest.mark.asyncio
async def test_openFonts(fileName,
                         features,
                         scripts,
                         languages,
                         axes,
                         text,
                         glyphNames):
    fontPath = getFontPath(fileName)
    numFonts, opener = getOpener(fontPath)
    assert numFonts(fontPath) == 1
    font, fontData = await opener(fontPath, 0)
    assert font.features == features
    assert font.scripts == scripts
    assert font.languages == languages
    assert font.axes == axes
    run = font.getGlyphRun(text)
    assert [gi.name for gi in run] == glyphNames
