from contextlib import redirect_stdout, redirect_stderr
import io
import logging
import re
import sys
from fontTools.pens.cocoaPen import CocoaPen
from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib import TTFont
from fontTools.ufoLib import UFOReader
from .baseFont import BaseFont
from ..misc.hbShape import HBShape
from ..misc.runInPool import runInProcessPool


class UFOFont(BaseFont):

    def __init__(self, fontPath):
        super().__init__()
        self.reader = UFOReader(fontPath)
        self.glyphSet = self.reader.getGlyphSet()
        self.info = UFOInfo()
        self.reader.readInfo(self.info)
        self._fontPath = fontPath
        self._cachedGlyphs = {}

    async def load(self):
        glyphOrder = sorted(self.glyphSet.keys())  # no need for the "real" glyph order
        if ".notdef" not in glyphOrder:
            # We need a .notdef glyph, so let's make one.
            glyphOrder.insert(0, ".notdef")
            glyph = NotDefGlyph(self.info.unitsPerEm)
            self._addOutlinePathToGlyph(glyph)
            self._cachedGlyphs[".notdef"] = glyph

        fontData, output = await runInProcessPool(compileMinimumFont_captureOutput, self._fontPath)
        if output:
            print(output, file=sys.stderr)
        f = io.BytesIO(fontData)
        self.ttFont = TTFont(f, lazy=True)
        self.shaper = HBShape(fontData, getAdvanceWidth=self._getAdvanceWidth, ttFont=self.ttFont)

    def _getGlyph(self, glyphName):
        glyph = self._cachedGlyphs.get(glyphName)
        if glyph is None:
            glyph = self.glyphSet[glyphName]
            self._addOutlinePathToGlyph(glyph)
            self._cachedGlyphs[glyphName] = glyph
        return glyph

    def _addOutlinePathToGlyph(self, glyph):
        pen = CocoaPen(self.glyphSet)
        glyph.draw(pen)
        glyph.outline = pen.path

    def _getAdvanceWidth(self, glyphName):
        glyph = self._getGlyph(glyphName)
        return glyph.width

    def _getOutlinePath(self, glyphName, colorLayers):
        glyph = self._getGlyph(glyphName)
        return glyph.outline


class UFOInfo:
    pass


class NotDefGlyph:

    def __init__(self, unitsPerEm):
        self.unitsPerEm = unitsPerEm
        self.width = unitsPerEm // 2
        self.height = unitsPerEm

    def draw(self, pen):
        inset = 0.05 * self.unitsPerEm
        sideBearing = 0.05 * self.unitsPerEm
        height = 0.75 * self.unitsPerEm
        xMin, yMin, xMax, yMax = sideBearing, sideBearing, self.width - sideBearing, height
        pen.moveTo((xMin, yMin))
        pen.lineTo((xMin, yMax))
        pen.lineTo((xMax, yMax))
        pen.lineTo((xMax, yMin))
        pen.closePath()
        xMin += inset
        yMin += inset
        xMax -= inset
        yMax -= inset
        pen.moveTo((xMin, yMin))
        pen.lineTo((xMax, yMin))
        pen.lineTo((xMax, yMax))
        pen.lineTo((xMin, yMax))
        pen.closePath()


_unicodeGLIFPattern = re.compile(re.compile(rb'<\s*unicode\s+hex\s*=\s*\"([0-9A-Fa-f]+)\"'))


def _getCharacterMapping(ufoPath, glyphSet):
    # This seems about three times faster than reader.getCharacterMapping()
    cmap = {}
    duplicateUnicodes = set()
    for glyphName in sorted(glyphSet.keys()):
        data = glyphSet.getGLIF(glyphName)
        if b"<!--" in data:
            # Use proper parser
            unicodes = fetchUnicodes(data)
        else:
            # Fast route with regex
            unicodes = [int(s, 16) for s in _unicodeGLIFPattern.findall(data)]
        for codePoint in unicodes:
            if codePoint not in cmap:
                cmap[codePoint] = glyphName
            else:
                duplicateUnicodes.add(codePoint)
    if duplicateUnicodes:
        logger = logging.getLogger("fontgoggles.font.ufoFont")
        logger.warning("Some code points in '%s' are assigned to multiple glyphs: %s", ufoPath, sorted(duplicateUnicodes))
    return cmap


def compileMinimumFont_captureOutput(ufoPath):
    f = io.StringIO()
    with redirect_stdout(f), redirect_stderr(f):
        data = compileMinimumFont(ufoPath)
    return data, f.getvalue()


def compileMinimumFont(ufoPath):
    """Compile the source UFO to a TTF with the smallest amount of tables
    needed to let HarfBuzz do its work. That would be 'cmap', 'post' and
    whatever OTL tables are needed for the features. Return the compiled
    font data.

    This function may do some redundant work (eg. we need an UFOReader
    elsewhere, too), but having a picklable argument and return value
    allows us to run it in a separate process, enabling parallelism.
    """
    reader = UFOReader(ufoPath)
    glyphSet = reader.getGlyphSet()
    info = UFOInfo()
    reader.readInfo(info)

    glyphOrder = sorted(glyphSet.keys())  # no need for the "real" glyph order
    if ".notdef" not in glyphOrder:
        # We need a .notdef glyph, so let's make one.
        glyphOrder.insert(0, ".notdef")
    cmap = _getCharacterMapping(ufoPath, glyphSet)
    fb = FontBuilder(info.unitsPerEm)
    fb.setupGlyphOrder(glyphOrder)
    fb.setupCharacterMap(cmap)
    fb.setupPost()  # This makes sure we store the glyph names
    features = reader.readFeatures()
    if features:
        fb.addOpenTypeFeatures(features, ufoPath)
    strm = io.BytesIO()
    fb.save(strm)
    return strm.getvalue()
