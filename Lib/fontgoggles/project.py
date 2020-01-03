from os import PathLike
from .font import getOpener


class FontLoader:

    def __init__(self):
        self.fonts = {}

    async def loadFont(self, fontKey, sharableFontData=None):
        if fontKey in self.fonts:
            return
        if sharableFontData is None:
            sharableFontData = {}
        path, fontNumber = fontKey
        fontData = sharableFontData.get(path)
        numFonts, opener, getSortInfo = getOpener(path)
        assert fontNumber < numFonts(path)
        font, fontData = await opener(path, fontNumber, fontData)
        if fontData is not None:
            sharableFontData[path] = fontData
        self.fonts[fontKey] = font

    def purgeFonts(self, usedKeys):
        self.fonts = {fontKey: fontObject for fontKey, fontObject in self.fonts.items()
                      if fontKey in usedKeys}


class FontItemInfo:

    def __init__(self, identifier, fontKey, fontLoader):
        self.identifier = identifier
        self.fontKey = fontKey
        self._fontLoader = fontLoader

    @property
    def font(self):
        return self._fontLoader.fonts.get(self.fontKey)
    
    async def load(self, sharableFontData=None):
        await self._fontLoader.loadFont(self.fontKey, sharableFontData)


class Project:

    def __init__(self):
        self.fonts = []
        self._fontLoader = FontLoader()
        self._fontItemIdentifierGenerator = self._fontItemIdentifierGeneratorFunc()

    def addFont(self, path: PathLike, fontNumber: int, index=None):
        if not isinstance(path, PathLike):
            raise TypeError("path must be a Path(-like) object")
        fontKey = (path, fontNumber)
        fontItemIdentifier = self.nextFontItemIdentifier()
        fontItemInfo = FontItemInfo(fontItemIdentifier, fontKey, self._fontLoader)
        if index is None:
            index = len(self.fonts)
        self.fonts.insert(index, fontItemInfo)

    async def loadFonts(self):
        # Note that this method cannot not load fonts concurrently, and
        # should be seen as a lazy convenience method, good enough for
        # testing.
        sharableFontData = {}
        for fontItemInfo in self.fonts:
            await fontItemInfo.load(sharableFontData)


    def nextFontItemIdentifier(self):
        return next(self._fontItemIdentifierGenerator)

    @staticmethod
    def _fontItemIdentifierGeneratorFunc():
        counter = 0
        while True:
            yield f"fontItem_{counter}"
            counter += 1

    def purgeFonts(self):
        """Remove font objects that are no longer referenced in the fontItems
        list.
        """
        usedKeys = {fii.fontKey for fii in self.fonts}
        self._fontLoader.purgeFonts(usedKeys)
