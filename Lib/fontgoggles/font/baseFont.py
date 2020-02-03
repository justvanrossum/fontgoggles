from ..misc.properties import cachedProperty
from ..misc.hbShape import characterGlyphMapping
from . import mergeScriptsAndLanguages


class BaseFont:

    def __init__(self, fontPath, fontNumber, dataProvider=None):
        self.fontPath = fontPath
        self.fontNumber = fontNumber
        self.resetCache()

    def resetCache(self):
        self._outlinePaths = [{}, {}]  # cache for (outline, colorLayers) objects
        self._currentVarLocation = None  # used to determine whether to purge the outline cache
        # Invalidate cached properties
        del self.unitsPerEm
        del self.colorPalettes
        del self.featuresGSUB
        del self.featuresGPOS
        del self.scripts
        del self.axes

    def close(self):
        pass

    async def load(self, outputWriter):
        pass

    def updateFontPath(self, newFontPath):
        """This gets called when the source file was moved."""
        self.fontPath = fontPath

    def getExternalFiles(self):
        """Subclasses may override this to return a list of external files,
        that clients can observe for changes.
        """
        return []

    def canReloadWithChange(self, externalFilePath):
        """ `externalFilePath` is None or an external file. If it is None,
        the main source file was changed on disk, else the externalFilePath
        was changed.

        This method should return True if it can update itself, in which case
        font.load() will be called. If it returns False, the font will be
        discarded and rebuilt from scratch.
        """
        return False

    @cachedProperty
    def unitsPerEm(self):
        return self.ttFont["head"].unitsPerEm

    @cachedProperty
    def colorPalettes(self):
        return [[(0, 0, 0, 1)]]  # default palette [[(r, g, b, a)]]

    @cachedProperty
    def featuresGSUB(self):
        return set(self.shaper.getFeatures("GSUB"))

    @cachedProperty
    def featuresGPOS(self):
        return set(self.shaper.getFeatures("GPOS"))

    @cachedProperty
    def scripts(self):
        gsub = self.shaper.getScriptsAndLanguages("GSUB")
        gpos = self.shaper.getScriptsAndLanguages("GPOS")
        return mergeScriptsAndLanguages(gsub, gpos)

    @cachedProperty
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

        glyphs = GlyphsRun(len(text), self.unitsPerEm, direction in ("TTB", "BTT"))
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

    def getGlyphRun(self, text, *, features=None, varLocation=None,
                    direction=None, language=None, script=None,
                    colorLayers=False):
        self.setVarLocation(varLocation)
        glyphInfo = self.shaper.shape(text, features=features, varLocation=varLocation,
                                      direction=direction, language=language, script=script)
        glyphNames = (gi.name for gi in glyphInfo)
        for glyph, path in zip(glyphInfo, self.getOutlinePaths(glyphNames, colorLayers)):
            glyph.path = path
        return glyphInfo

    def setVarLocation(self, varLocation):
        axes = self.axes
        if varLocation:
            # subset to our own axes
            varLocation = {k: v for k, v in varLocation.items() if k in axes}
        if self._currentVarLocation != varLocation:
            self._purgeCaches()
            self._currentVarLocation = varLocation
            self.varLocationChanged(varLocation)

    def getOutlinePaths(self, glyphNames, colorLayers=False):
        for glyphName in glyphNames:
            outline = self._outlinePaths[colorLayers].get(glyphName)
            if outline is None:
                outline = self._getOutlinePath(glyphName, colorLayers)
                self._outlinePaths[colorLayers][glyphName] = outline
            yield outline

    def _purgeCaches(self):
        self._outlinePaths = [{}, {}]

    def _getOutlinePath(self, glyphName, colorLayers):
        raise NotImplementedError()

    def varLocationChanged(self, varLocation):
        # Optional override
        pass


class GlyphsRun(list):

    def __init__(self, numChars, unitsPerEm, vertical):
        self.numChars = numChars
        self.unitsPerEm = unitsPerEm
        self.vertical = vertical
        self._glyphToChars = None
        self._charToGlyphs = None
        self.endPos = (0, 0)

    def mapGlyphsToChars(self, glyphIndices):
        if self._glyphToChars is None:
            self._calcMappings()
        glyphToChars = self._glyphToChars
        return {ci for gi in glyphIndices for ci in glyphToChars[gi]}

    def mapCharsToGlyphs(self, charIndices):
        if self._charToGlyphs is None:
            self._calcMappings()
        charToGlyphs = self._charToGlyphs
        return {gi for ci in charIndices for gi in charToGlyphs[ci]}

    def _calcMappings(self):
        clusters = [glyphInfo.cluster for glyphInfo in self]
        self._glyphToChars, self._charToGlyphs = characterGlyphMapping(clusters, self.numChars)
