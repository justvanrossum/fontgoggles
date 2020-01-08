import json
from os import PathLike
import os
import pathlib
from .font import getOpener


class Project:

    def __init__(self):
        self.fonts = []
        self._fontLoader = FontLoader()
        self._fontItemIdentifierGenerator = self._fontItemIdentifierGeneratorFunc()

    @classmethod
    def loads(cls, data, rootPath):
        root = json.loads(data)
        self = cls()
        for fontItemInfoDict in root["fonts"]:
            fontPath = pathlib.Path(os.path.abspath(os.path.join(rootPath, fontItemInfoDict["path"])))
            self.addFont(fontPath, fontItemInfoDict["fontNumber"])
        return self

    def asJSON(self, rootPath):
        root = self.asDict(rootPath)
        return json.dumps(root, indent=2, ensure_ascii=False).encode("utf=8")

    def asDict(self, rootPath):
        root = {}
        root["fonts"] = []
        root["settings"] = {}
        for fontItemInfo in self.fonts:
            fontPath, fontNumber = fontItemInfo.fontKey
            relFontPath = os.path.relpath(fontPath, rootPath)
            fontItemInfoDict = dict(path=relFontPath, fontNumber=fontNumber)
            root["fonts"].append(fontItemInfoDict)
        return root

    def addFont(self, path: PathLike, fontNumber: int, index=None):
        fontItemInfo = self.newFontItemInfo(path, fontNumber)
        if index is None:
            index = len(self.fonts)
        self.fonts.insert(index, fontItemInfo)

    def newFontItemInfo(self, path: PathLike, fontNumber: int):
        if not isinstance(path, PathLike):
            raise TypeError("path must be a Path(-like) object")
        fontKey = (path, fontNumber)
        fontItemIdentifier = self._nextFontItemIdentifier()
        return FontItemInfo(fontItemIdentifier, fontKey, self._fontLoader)

    async def loadFonts(self):
        # Note that this method cannot not load fonts concurrently, and
        # should be seen as a lazy convenience method, good enough for
        # testing.
        sharableFontData = {}
        for fontItemInfo in self.fonts:
            await fontItemInfo.load(sharableFontData)

    def _nextFontItemIdentifier(self):
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
