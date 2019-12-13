import pathlib
from typing import Dict, Optional, Tuple, Union
from .font import getOpener
from .font.baseFont import BaseFont


class Project:

    fonts: Dict[Tuple[pathlib.Path,int], Optional[BaseFont]]

    def __init__(self):
        self.fonts = {}

    def addFont(self, path:pathlib.Path, fontNumber:int):
        self.fonts[path, fontNumber] = None

    def getFont(self, path:pathlib.Path, fontNumber:int):
        font = self.fonts[path, fontNumber]
        if font is None:
            raise ValueError("font is not loaded")
        return font

    async def loadFont(self, path:pathlib.Path, fontNumber:int,
                       sharableFontData:dict=None):
        font = self.fonts[path, fontNumber]
        if font is not None:
            return
        if sharableFontData is None:
            sharableFontData = {}
        fontData = sharableFontData.get(path)
        numFonts, opener = getOpener(path)
        assert fontNumber < numFonts
        font, fontData = await opener(path, fontNumber, fontData)
        if fontData is not None:
            sharableFontData[path] = fontData
        self.fonts[path, fontNumber] = font

    async def loadFonts(self):
        sharableFontData = {}
        for (path, fontNumber) in self.fonts:
            await self.loadFont(path, fontNumber, sharableFontData)
