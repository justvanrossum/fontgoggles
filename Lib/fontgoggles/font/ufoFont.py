import io
import sys
from types import SimpleNamespace
from fontTools.pens.cocoaPen import CocoaPen
from fontTools.ttLib import TTFont
from fontTools.ufoLib import UFOReader
from fontTools.ufoLib.glifLib import Glyph as GLIFGlyph
from .baseFont import BaseFont
from ..misc.compilerPool import compileUFOToBytes
from ..misc.hbShape import HBShape
from ..misc.properties import readOnlyCachedProperty


class UFOFont(BaseFont):

    def __init__(self, fontPath, needsShaper=True):
        super().__init__()
        self.updateFontPath(fontPath)
        self.info = SimpleNamespace()
        self.reader.readInfo(self.info)
        self._fontPath = fontPath
        self._cachedGlyphs = {}

    def updateFontPath(self, newFontPath):
        """This also gets called when the source file was moved."""
        self.reader = UFOReader(newFontPath)
        self.glyphSet = self.reader.getGlyphSet()
        self.glyphSet.glyphClass = Glyph

    async def load(self, outputWriter):
        glyphOrder = sorted(self.glyphSet.keys())  # no need for the "real" glyph order
        if ".notdef" not in glyphOrder:
            # We need a .notdef glyph, so let's make one.
            glyphOrder.insert(0, ".notdef")
            glyph = NotDefGlyph(self.info.unitsPerEm)
            self._addOutlinePathToGlyph(glyph)
            self._cachedGlyphs[".notdef"] = glyph

        fontData, error = await compileUFOToBytes(self._fontPath, outputWriter)

        if fontData is None:
            # TODO: deal with error
            # TODO: this cannot work down the line, how to handle?
            self.ttFont = None
            self.shaper = None
        else:
            f = io.BytesIO(fontData)
            self.ttFont = TTFont(f, lazy=True)
            self.shaper = HBShape(fontData,
                                  getHorizontalAdvance=self._getHorizontalAdvance,
                                  getVerticalAdvance=self._getVerticalAdvance,
                                  getVerticalOrigin=self._getVerticalOrigin,
                                  ttFont=self.ttFont)

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

    def _getHorizontalAdvance(self, glyphName):
        glyph = self._getGlyph(glyphName)
        return glyph.width

    @readOnlyCachedProperty
    def defaultVerticalAdvance(self):
        ascender = getattr(self.info, "ascender", None)
        descender = getattr(self.info, "descender", None)
        if ascender is None or descender is None:
            return self.info.unitsPerEm
        else:
            return ascender + abs(descender)

    @readOnlyCachedProperty
    def defaultVerticalOriginY(self):
        ascender = getattr(self.info, "ascender", None)
        if ascender is None:
            return self.info.unitsPerEm  # ???
        else:
            return ascender

    def _getVerticalAdvance(self, glyphName):
        glyph = self._getGlyph(glyphName)
        vAdvance = glyph.height
        if vAdvance is None or vAdvance == 0:  # XXX default vAdv == 0 -> bad UFO spec
            vAdvance = self.defaultVerticalAdvance
        return -abs(vAdvance)

    def _getVerticalOrigin(self, glyphName):
        glyph = self._getGlyph(glyphName)
        vOrgX = glyph.width / 2
        lib = getattr(glyph, "lib", {})
        vOrgY = lib.get("public.verticalOrigin")
        if vOrgY is None:
            vOrgY = self.defaultVerticalOriginY
        return True, vOrgX, vOrgY

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
