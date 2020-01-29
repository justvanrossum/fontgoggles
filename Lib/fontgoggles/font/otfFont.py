import io
from fontTools.ttLib import TTFont
from ..misc.ftFont import FTFont
from ..misc.hbShape import HBShape
from .baseFont import BaseFont


class OTFFont(BaseFont):

    @classmethod
    def fromPath(cls, fontPath, fontNumber, fontData=None):
        if fontData is None:
            with open(fontPath, "rb") as f:
                fontData = f.read()
        self = cls(fontData, fontNumber)
        return self

    def __init__(self, fontData, fontNumber):
        super().__init__()
        self.fontData = fontData
        f = io.BytesIO(fontData)
        self.ttFont = TTFont(f, fontNumber=fontNumber, lazy=True)
        if self.ttFont.flavor in ("woff", "woff2"):
            self.ttFont.flavor = None
            self.ttFont.recalcBBoxes = False
            self.ttFont.recalcTimestamp = False
            f = io.BytesIO()
            self.ttFont.save(f, reorderTables=False)
            fontData = f.getvalue()
        self.ftFont = FTFont(fontData, fontNumber=fontNumber, ttFont=self.ttFont)
        self.shaper = HBShape(fontData, fontNumber=fontNumber, ttFont=self.ttFont)

    def _getOutlinePath(self, glyphName, colorLayers):
        outline = self.ftFont.getOutlinePath(glyphName)
        if colorLayers:
            return [(outline, 0)]
        else:
            return outline

    def varLocationChanged(self, varLocation):
        self.ftFont.setVarLocation(varLocation if varLocation else {})


class TTXFont(OTFFont):

    def __init__(self, fontPath, fontNumber):
        BaseFont.__init__()  # not calling OTFFont.__init__
        self.fontPath = fontPath
        self.fontNumber = fontNumber

    async def load(self):
        self.ttFont = TTFont()
        self.ttFont.fromXML(self.fontPath)
        f = io.BytesIO()
        self.ttFont.save(f, reorderTables=False)
        fontData = f.getvalue()
        self.ftFont = FTFont(fontData, fontNumber=self.fontNumber, ttFont=self.ttFont)
        self.shaper = HBShape(fontData, fontNumber=self.fontNumber, ttFont=self.ttFont)
