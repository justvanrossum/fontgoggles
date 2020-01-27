import io
import sys
from fontTools.pens.cocoaPen import CocoaPen
from fontTools.ttLib import TTFont
from fontTools.ufoLib import UFOReader
from fontTools.ufoLib.glifLib import Glyph as GLIFGlyph
from .baseFont import BaseFont
from ..misc.hbShape import HBShape
from ..misc.ufoCompiler import UFOInfo
from ..misc.compilerPool import compileUFOToBytes


class UFOFont(BaseFont):

    def __init__(self, fontPath, needsShaper=True):
        super().__init__()
        self.reader = UFOReader(fontPath)
        self.glyphSet = self.reader.getGlyphSet()
        self.glyphSet.glyphClass = Glyph
        self.info = UFOInfo()
        self.reader.readInfo(self.info)
        self._fontPath = fontPath
        self._cachedGlyphs = {}
        self._needsShaper = needsShaper  # TODO: could be arg to self.load()

    async def load(self):
        glyphOrder = sorted(self.glyphSet.keys())  # no need for the "real" glyph order
        if ".notdef" not in glyphOrder:
            # We need a .notdef glyph, so let's make one.
            glyphOrder.insert(0, ".notdef")
            glyph = NotDefGlyph(self.info.unitsPerEm)
            self._addOutlinePathToGlyph(glyph)
            self._cachedGlyphs[".notdef"] = glyph

        fontData, output, error = await compileUFOToBytes(self._fontPath)

        if output or error:
            # TODO: where/how to report to the user?
            print("----- ", self._fontPath, file=sys.stderr)
            print(output, file=sys.stderr)
        if fontData is None:
            # TODO: this cannot work down the line, how to handle?
            self.ttFont = None
            self.shaper = None
        else:
            f = io.BytesIO(fontData)
            self.ttFont = TTFont(f, lazy=True)
            if self._needsShaper:
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

    def setVarLocation(self, varLocation):
        # For compatibility with dsFont.VarGlyph
        pass

    def getOutline(self):
        pen = CocoaPen(None)  # by now there are no more composites
        self.draw(pen)
        return pen.path


class Glyph(GLIFGlyph):
    width = 0
    height = None
