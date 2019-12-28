import io
from fontTools.ttLib import TTFont
from ..misc.properties import readOnlyCachedProperty
from ..misc.hbShape import HBShape
from ..misc.ftFont import FTFont
from ..misc.hbShape import characterGlyphMapping
from . import mergeScriptsAndLanguages


class BaseFont:

    def __init__(self):
        self._outlinePaths = [{}, {}]  # cache for (outline, colorLayers) objects
        self._currentVarLocation = None  # used to determine whether to purge the outline cache

    def close(self):
        pass

    @readOnlyCachedProperty
    def unitsPerEm(self):
        return self.ttFont["head"].unitsPerEm

    @readOnlyCachedProperty
    def colorPalettes(self):
        return [[(0, 0, 0, 1)]]  # default palette [[(r, g, b, a)]]

    @readOnlyCachedProperty
    def featuresGSUB(self):
        return set(self.shaper.getFeatures("GSUB"))

    @readOnlyCachedProperty
    def featuresGPOS(self):
        return set(self.shaper.getFeatures("GPOS"))

    @readOnlyCachedProperty
    def scripts(self):
        gsub = self.shaper.getScriptsAndLanguages("GSUB")
        gpos = self.shaper.getScriptsAndLanguages("GPOS")
        return mergeScriptsAndLanguages(gsub, gpos)

    @readOnlyCachedProperty
    def axes(self):
        fvar = self.ttFont.get("fvar")
        if fvar is None:
            return {}
        name = self.ttFont["name"]
        axes = {}
        for axis in fvar.axes:
            axisDict = dict(name=str(name.getName(axis.axisNameID, 3, 1)),
                            minValue=axis.minValue,
                            defaultValue=axis.defaultValue,
                            maxValue=axis.maxValue)
            axes[axis.axisTag] = axisDict
        return axes

    def getGlyphRunFromTextInfo(self, textInfo, **kwargs):
        text = textInfo.text
        runLengths = textInfo.runLengths
        direction = textInfo.directionForShaper
        script = textInfo.scriptOverride
        language = textInfo.languageOverride

        glyphs = GlyphsRun(len(text), self.unitsPerEm)
        index = 0
        for rl in runLengths:
            seg = text[index:index + rl]
            run = self.getGlyphRun(seg,
                                   direction=direction,
                                   script=script,
                                   language=language,
                                   **kwargs)
            for gi in run:
                gi.cluster += index
            glyphs.extend(run)
            index += rl
        assert index == len(text)
        x = y = 0
        for gi in glyphs:
            gi.pos = x + gi.dx, y + gi.dy
            x += gi.ax
            y += gi.ay
        glyphs.endPos = (x, y)
        return glyphs

    def getGlyphRun(self, txt, *, features=None, varLocation=None,
                    direction=None, language=None, script=None,
                    colorLayers=False):
        glyphInfo = self.shape(txt, features=features, varLocation=varLocation,
                               direction=direction, language=language,
                               script=script)
        glyphNames = (gi.name for gi in glyphInfo)
        for glyph, path in zip(glyphInfo, self.getOutlinePaths(glyphNames, varLocation, colorLayers)):
            glyph.path = path
        return glyphInfo

    def shape(self, text, *, features, varLocation, direction, language, script):
        return self.shaper.shape(text, features=features, varLocation=varLocation,
                                 direction=direction, language=language, script=script)

    def getOutlinePaths(self, glyphNames, varLocation, colorLayers=False):
        axes = self.axes
        if varLocation:
            # subset to our own axes
            varLocation = {k: v for k, v in varLocation.items() if k in axes}
        if self._currentVarLocation != varLocation:
            # purge outline cache
            self._outlinePaths = [{}, {}]
            self._currentVarLocation = varLocation
            self._setVarLocation(varLocation)
        for glyphName in glyphNames:
            outline = self._outlinePaths[colorLayers].get(glyphName)
            if outline is None:
                outline = self._getOutlinePath(glyphName, colorLayers)
                self._outlinePaths[colorLayers][glyphName] = outline
            yield outline

    def _getOutlinePath(self, glyphName, colorLayers):
        raise NotImplementedError()

    def _setVarLocation(self, varLocation):
        pass  # optional override


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
        self.ftFont = FTFont(fontData, fontNumber=fontNumber, ttFont=self.ttFont)
        self.shaper = HBShape(fontData, fontNumber=fontNumber, ttFont=self.ttFont)

    def _getOutlinePath(self, glyphName, colorLayers):
        outline = self.ftFont.getOutlinePath(glyphName)
        if colorLayers:
            return [(outline, 0)]
        else:
            return outline

    def _setVarLocation(self, varLocation):
        self.ftFont.setVarLocation(varLocation if varLocation else {})


class GlyphsRun(list):

    def __init__(self, numChars, unitsPerEm):
        self.numChars = numChars
        self.unitsPerEm = unitsPerEm
        self._glyphToChars = None
        self._charToGlyphs = None

    def mapGlyphsToChars(self, glyphIndices):
        glyphToChars = self.glyphToChars
        return {ci for gi in glyphIndices for ci in glyphToChars[gi]}

    def mapCharsToGlyphs(self, charIndices):
        charToGlyphs = self.charToGlyphs
        return {gi for ci in charIndices for gi in charToGlyphs[ci]}

    def _calcMappings(self):
        clusters = [glyphInfo.cluster for glyphInfo in self]
        self._glyphToChars, self._charToGlyphs = characterGlyphMapping(clusters, self.numChars)

    @property
    def glyphToChars(self):
        if self._glyphToChars is None:
            self._calcMappings()
        return self._glyphToChars

    @property
    def charToGlyphs(self):
        if self._charToGlyphs is None:
            self._calcMappings()
        return self._charToGlyphs
