import io
import logging
import re
from fontTools.pens.cocoaPen import CocoaPen
from fontTools.fontBuilder import FontBuilder
from fontTools.ufoLib import UFOReader
from .baseFont import BaseFont
from ..misc.hbShape import HBShape


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
        cmap = _getCharacterMapping(self._fontPath, self.glyphSet)
        fb = FontBuilder(self.info.unitsPerEm)
        fb.setupGlyphOrder(glyphOrder)
        fb.setupCharacterMap(cmap)
        # Without a 'post' table, the font will not contain the right glyph names,
        # but that's ok if we pass our own ttf to HBShape, which will then be used
        # to convert glyph IDs to glyph names.
        # fb.setupPost()
        features = self.reader.readFeatures()
        if features:
            fb.addOpenTypeFeatures(features, self._fontPath)
        strm = io.BytesIO()
        fb.save(strm)
        self.ttFont = fb.font
        fontData = strm.getvalue()
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
