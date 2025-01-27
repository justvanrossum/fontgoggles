import io
from fontTools.ttLib import TTFont
from .baseFont import BaseFont
from .glyphDrawing import GlyphDrawing, GlyphLayersDrawing, GlyphCOLRv1Drawing
from ..compile.compilerPool import compileTTXToBytes
from ..misc.hbShape import HBShape
from ..misc.properties import cachedProperty
from ..misc.platform import platform


class _OTFBaseFont(BaseFont):

    def _getGlyphOutline(self, name):
        return platform.pathFromGlyph(self.shaper.font, self.shaper.glyphMap[name])

    def _getGlyphDrawing(self, glyphName, colorLayers):
        if "VarC" in self.ttFont:
            pen = platform.Pen(None)
            location = self._currentVarLocation or {}
            self.varcFont.drawGlyph(pen, glyphName, location)
            return GlyphDrawing(pen.path)
        if colorLayers:
            if self.colorLayers is not None:
                layers = self.colorLayers.get(glyphName)
                if layers is not None:
                    drawingLayers = [(self._getGlyphOutline(layer.name), layer.colorID)
                                     for layer in layers]
                    return GlyphLayersDrawing(drawingLayers)
            elif self.colorFont is not None:
                return GlyphCOLRv1Drawing(glyphName, self.colorFont)

        outline = self._getGlyphOutline(glyphName)
        return GlyphDrawing(outline)

    def varLocationChanged(self, varLocation):
        if self.colorFont is not None:
            self.colorFont.setLocation(varLocation)

    @cachedProperty
    def colorLayers(self):
        colrTable = self.ttFont.get("COLR")
        if colrTable is not None and colrTable.version == 0:
            return colrTable.ColorLayers
        return None

    @cachedProperty
    def colorPalettes(self):
        cpalTable = self.ttFont.get("CPAL")
        if cpalTable is not None:
            palettes = []
            for paletteRaw in cpalTable.palettes:
                palette = [(color.red/255, color.green/255, color.blue/255, color.alpha/255)
                           for color in paletteRaw]
                palettes.append(palette)
            return palettes
        else:
            return None

    @cachedProperty
    def colorFont(self):
        colrTable = self.ttFont.get("COLR")
        if colrTable is not None and colrTable.version == 1:
            from blackrenderer.font import BlackRendererFont

            return BlackRendererFont(self.fontPath, fontNumber=self.fontNumber)
        return None

    @cachedProperty
    def varcFont(self):
        from fontTools.ttLib import registerCustomTableClass
        from rcjktools.ttVarCFont import TTVarCFont
        registerCustomTableClass("VarC", "rcjktools.table_VarC", "table_VarC")
        return TTVarCFont(None, ttFont=self.ttFont, hbFont=self.shaper.font)


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
