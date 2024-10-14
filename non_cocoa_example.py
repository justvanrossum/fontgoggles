from fontgoggles.font import getOpener
from fontgoggles.font.baseFont import BaseFont
from fontgoggles.misc.textInfo import TextInfo

from pathlib import Path
from asyncio import run

font_path = Path("~/Type/fonts/fonts/__variables2/PolymathVar.ttf").expanduser()

numFonts, opener, getSortInfo = getOpener(font_path)
font:BaseFont = opener(font_path, 0)
run(font.load(None))

textInfo = TextInfo("abc")
glyphs = font.getGlyphRunFromTextInfo(textInfo)
glyphNames = [g.name for g in glyphs]
glyphDrawings = list(font.getGlyphDrawings(glyphNames, True))

print(glyphDrawings[0].path)