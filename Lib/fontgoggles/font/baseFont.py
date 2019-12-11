import asyncio
import io
from fontTools.ttLib import TTFont
from ..misc.decorators import readOnlyCachedProperty
from ..misc.hbShape import HBShape
from ..misc.ftFont import FTFont


class BaseFont:

    # TODO: how to load from .ttc

    @classmethod
    async def fromPath(cls, fontPath):
        self = cls(fontPath)
        await self._async_init()
        return self

    def __init__(self, fontPath):
        self.fontPath = fontPath
        self.fontNumber = 0  # TODO .ttc/.otc
        self._outlinePaths = [{}, {}]  # cache for (outline, colorLayers) objects
        self._currentVarLocation = None  # used to determine whether to purge the outline cache

    async def _async_init(self):
        fontData = await self._getFontData()
        await self._loadWithFontData(fontData)

    async def _loadWithFontData(self, fontData):
        ff = io.BytesIO(fontData)
        self.ttFont = TTFont(ff, fontNumber=self.fontNumber, lazy=True)
        self.shaper = self._getShaper(fontData)

    def close(self):
        pass

    async def _getFontData(self):
        raise NotImplementedError()

    def _getShaper(self):
        raise NotImplementedError()

    @readOnlyCachedProperty
    def colorPalettes(self):
        return [[(0, 0, 0, 1)]]  # default palette [[(r, g, b, a)]]  

    @readOnlyCachedProperty
    def features(self):
        return sorted(set(self.shaper.getFeatures("GSUB") + self.shaper.getFeatures("GPOS")))

    @readOnlyCachedProperty
    def languages(self):
        return sorted(set(self.shaper.getLanguages("GSUB") + self.shaper.getLanguages("GPOS")))

    @readOnlyCachedProperty
    def scripts(self):
        return sorted(set(self.shaper.getScripts("GSUB") + self.shaper.getScripts("GPOS")))

    @readOnlyCachedProperty
    def axes(self):
        fvar = self.ttFont.get("fvar")
        if fvar is None:
            return []
        name = self.ttFont["name"]
        axes = []
        for axis in fvar.axes:
            axisDict = dict(tag=axis.axisTag,
                            name=str(name.getName(axis.axisNameID, 3, 1)),
                            minValue=axis.minValue,
                            defaultValue=axis.defaultValue,
                            maxValue=axis.maxValue)
            axes.append(axisDict)
        return axes

    async def getGlyphRun(self, txt, *, features=None, variations=None,
                          direction=None, language=None, script=None,
                          colorLayers=False):
        glyphPositioning = self.shape(txt, features=features, variations=variations,
                                      direction=direction, language=language,
                                      script=script)
        await asyncio.sleep(0)
        glyphNames = (gi.name for gi in glyphPositioning)
        paths = []
        async for path in self.getOutlinePaths(glyphNames, variations, colorLayers):
            paths.append(path)
        return zip(glyphPositioning, paths)

    def shape(self, text, *, features, variations, direction, language, script):
        return self.shaper.shape(text, features=features, variations=variations,
                                 direction=direction, language=language, script=script)

    async def getOutlinePaths(self, glyphNames, variations, colorLayers=False):
        if self._currentVarLocation != variations:
            # purge outline cache
            self._outlinePaths =[{}, {}]
            self._currentVarLocation = variations
        for glyphName in glyphNames:
            outline = self._outlinePaths[colorLayers].get(glyphName)
            if outline is None:
                outline = await self._getOutlinePath(glyphName, colorLayers)
                self._outlinePaths[colorLayers][glyphName] = outline
            yield outline

    async def _getOutlinePath(self, glyphName, colorLayers):
        raise NotImplementedError()


class OTFFont(BaseFont):

    async def _loadWithFontData(self, fontData):
        await super()._loadWithFontData(fontData)
        self.ftFont = FTFont(fontData, fontNumber=self.fontNumber, ttFont=self.ttFont)

    async def _getFontData(self):
        with open(self.fontPath, "rb") as f:
            return f.read()

    def _getShaper(self, fontData):
        return HBShape(fontData, fontNumber=self.fontNumber, ttFont=self.ttFont)

    async def _getOutlinePath(self, glyphName, colorLayers):
        outline = self.ftFont.getOutlinePath(glyphName)
        if colorLayers:
            return [(outline, 0)]
        else:
            return outline


class UFOFont(BaseFont):
    ...


class DesignSpaceFont(BaseFont):
    ...
