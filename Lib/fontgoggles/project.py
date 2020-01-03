from os import PathLike
from typing import Dict, Optional, Tuple
from .font import getOpener
from .font.baseFont import BaseFont


_RAISE_NOT_LOADED_ERROR = object()


class Project:

    fonts: Dict[Tuple[PathLike, int], Optional[BaseFont]]

    def __init__(self):
        self.fonts = {}
        self.fontItems = []
        self._fontItemIdentifierGenerator = self._fontItemIdentifierGeneratorFunc()

    def addFont(self, path: PathLike, fontNumber: int):
        if not isinstance(path, PathLike):
            raise TypeError("path must be a Path(-like) object")
        fontKey = (path, fontNumber)
        self.fonts[fontKey] = None
        fontItem = dict(id=self.nextFontItemIdentifier(),
                        fontKey=fontKey)
        self.fontItems.append(fontItem)

    def getFont(self, path: PathLike, fontNumber: int,
                notLoadedDefault=_RAISE_NOT_LOADED_ERROR):
        font = self.fonts[path, fontNumber]
        if font is None:
            if notLoadedDefault is _RAISE_NOT_LOADED_ERROR:
                raise ValueError("font is not loaded")
            else:
                return notLoadedDefault
        return font

    async def loadFont(self, path: PathLike, fontNumber: int,
                       sharableFontData=None):
        font = self.fonts[path, fontNumber]
        if font is not None:
            return
        if sharableFontData is None:
            sharableFontData = {}
        fontData = sharableFontData.get(path)
        numFonts, opener, getSortInfo = getOpener(path)
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

    def nextFontItemIdentifier(self):
        return next(self._fontItemIdentifierGenerator)

    @staticmethod
    def _fontItemIdentifierGeneratorFunc():
        counter = 0
        while True:
            yield f"fontItem_{counter}"
            counter += 1
