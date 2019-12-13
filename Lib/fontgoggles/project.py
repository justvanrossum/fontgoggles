import pathlib
from typing import Dict, Optional, Tuple, Union
from .font import getOpener
from .font.baseFont import BaseFont


_RAISE_NOT_LOADED_ERROR = object()


class Project:

    fonts: Dict[Tuple[pathlib.Path,int], Optional[BaseFont]]

    def __init__(self):
        self.fonts = {}

    def iterFontKeys(self):
        return iter(self.fonts)

    def addFont(self, path:pathlib.Path, fontNumber:int):
        self.fonts[path, fontNumber] = None

    def getFont(self, path:pathlib.Path, fontNumber:int,
                notLoadedDefault=_RAISE_NOT_LOADED_ERROR):
        font = self.fonts[path, fontNumber]
        if font is None:
            if notLoadedDefault is _RAISE_NOT_LOADED_ERROR:
                raise ValueError("font is not loaded")
            else:
                return notLoadedDefault
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
        assert fontNumber < numFonts(path)
        font, fontData = await opener(path, fontNumber, fontData)
        if fontData is not None:
            sharableFontData[path] = fontData
        self.fonts[path, fontNumber] = font

    async def loadFonts(self):
        # Note that this method cannot not load fonts concurrently, and
        # should be seen as a lazy convenience method, good enough for
        # testing.
        sharableFontData = {}
        for (path, fontNumber) in self.fonts:
            await self.loadFont(path, fontNumber, sharableFontData)
