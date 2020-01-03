from os import PathLike
from typing import Dict, Optional, Tuple
from .font import getOpener
from .font.baseFont import BaseFont


class Project:

    fonts: Dict[Tuple[PathLike, int], Optional[BaseFont]]

    def __init__(self):
        self.fonts = {}  # Fonts that are or will be loaded
        self.fontItems = []  # A list representing the font items we're looking at
        self._fontItemIdentifierGenerator = self._fontItemIdentifierGeneratorFunc()

    def addFont(self, path: PathLike, fontNumber: int, index=None):
        if not isinstance(path, PathLike):
            raise TypeError("path must be a Path(-like) object")
        fontKey = (path, fontNumber)
        self.fonts[fontKey] = None
        fontItemInfo = dict(id=self.nextFontItemIdentifier(),
                        fontKey=fontKey)
        if index is None:
            index = len(self.fontItems)
        self.fontItems.insert(index, fontItemInfo)

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

    def purgeFonts(self):
        """Remove font objects that are no longer referenced in the fontItems
        list.
        """
        usedKeys = {fii["fontKey"] for fii in self.fontItems}
        self.fonts = {fontKey: fontObject for fontKey, fontObject in self.fonts.items()
                      if fontKey in usedKeys}

    def nextFontItemIdentifier(self):
        return next(self._fontItemIdentifierGenerator)

    @staticmethod
    def _fontItemIdentifierGeneratorFunc():
        counter = 0
        while True:
            yield f"fontItem_{counter}"
            counter += 1
