import io
from fontTools.ttLib import TTFont
from .baseFont import BaseFont
from .glyphDrawing import GlyphDrawing, GlyphLayersDrawing
from ..compile.compilerPool import compileTTXToBytes
from ..misc.ftFont import FTFont
from ..misc.hbShape import HBShape
from ..misc.properties import cachedProperty


class _OTFBaseFont(BaseFont):

    def _getGlyphDrawing(self, glyphName, colorLayers):
        if colorLayers and "COLR" in self.ttFont:
            colorLayers = self.ttFont["COLR"].ColorLayers
            layers = colorLayers.get(glyphName)
            if layers is not None:
                drawingLayers = [(self.ftFont.getOutlinePath(layer.name), layer.colorID)
                                 for layer in layers]
                return GlyphLayersDrawing(drawingLayers)
        outline = self.ftFont.getOutlinePath(glyphName)
        return GlyphDrawing(outline)

    def varLocationChanged(self, varLocation):
        self.ftFont.setVarLocation(varLocation if varLocation else {})

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
        self.ftFont = FTFont(fontData, fontNumber=self.fontNumber, ttFont=self.ttFont)
        self.shaper = HBShape(fontData, fontNumber=self.fontNumber, ttFont=self.ttFont)


class TTXFont(_OTFBaseFont):

    async def load(self, outputWriter):
        fontData = await compileTTXToBytes(self.fontPath, outputWriter)
        f = io.BytesIO(fontData)
        self.ttFont = TTFont(f, fontNumber=self.fontNumber, lazy=True)
        self.ftFont = FTFont(fontData, fontNumber=self.fontNumber, ttFont=self.ttFont)
        self.shaper = HBShape(fontData, fontNumber=self.fontNumber, ttFont=self.ttFont)
