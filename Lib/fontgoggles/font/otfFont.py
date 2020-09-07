import io
from fontTools.ttLib import TTFont
from fontTools.pens.cocoaPen import CocoaPen
from .baseFont import BaseFont
from .glyphDrawing import GlyphDrawing
from ..compile.compilerPool import compileTTXToBytes
from ..misc.hbShape import HBShape
from ..misc.properties import cachedProperty


class _OTFBaseFont(BaseFont):

    def _getGlyphOutline(self, name):
        pen = CocoaPen(None)
        self.shaper.font.draw_glyph_with_pen(self.shaper.glyphMap[name], pen)
        return pen.path

    def _getGlyphDrawing(self, glyphName, colorLayers):
        if colorLayers and "COLR" in self.ttFont:
            colorLayers = self.ttFont["COLR"].ColorLayers
            layers = colorLayers.get(glyphName)
            if layers is not None:
                drawingLayers = [(self._getGlyphOutline(layer.name), layer.colorID)
                                 for layer in layers]
                return GlyphDrawing(drawingLayers)
        outline = self._getGlyphOutline(glyphName)
        return GlyphDrawing([(outline, None)])

    def varLocationChanged(self, varLocation):
        self.shaper.font.set_variations(varLocation if varLocation else {})

    @cachedProperty
    def colorPalettes(self):
        if "CPAL" in self.ttFont:
            palettes = []
            for paletteRaw in self.ttFont["CPAL"].palettes:
                palette = [(color.red/255, color.green/255, color.blue/255, color.alpha/255)
                           for color in paletteRaw]
                palettes.append(palette)
            return palettes
        else:
            return None


class OTFFont(_OTFBaseFont):

    def __init__(self, fontPath, fontNumber, dataProvider=None):
        super().__init__(fontPath, fontNumber)
        if dataProvider is not None:
            # This allows us for TTC fonts to share their raw data
            self.fontData = dataProvider.getData(fontPath)
        else:
            with open(fontPath, "rb") as f:
                self.fontData = f.read()

    async def load(self, outputWriter):
        fontData = self.fontData
        f = io.BytesIO(fontData)
        self.ttFont = TTFont(f, fontNumber=self.fontNumber, lazy=True)
        if self.ttFont.flavor in ("woff", "woff2"):
            self.ttFont.flavor = None
            self.ttFont.recalcBBoxes = False
            self.ttFont.recalcTimestamp = False
            f = io.BytesIO()
            self.ttFont.save(f, reorderTables=False)
            fontData = f.getvalue()
        self.shaper = HBShape(fontData, fontNumber=self.fontNumber, ttFont=self.ttFont)


class TTXFont(_OTFBaseFont):

    async def load(self, outputWriter):
        fontData = await compileTTXToBytes(self.fontPath, outputWriter)
        f = io.BytesIO(fontData)
        self.ttFont = TTFont(f, fontNumber=self.fontNumber, lazy=True)
        self.shaper = HBShape(fontData, fontNumber=self.fontNumber, ttFont=self.ttFont)
