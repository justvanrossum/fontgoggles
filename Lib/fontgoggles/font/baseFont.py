import logging
from ..misc.properties import cachedProperty
from ..misc.hbShape import characterGlyphMapping
from . import mergeScriptsAndLanguages


class BaseFont:

    def __init__(self, fontPath, fontNumber, dataProvider=None):
        self.fontPath = fontPath
        self.fontNumber = fontNumber
        self.nameInCollection = None
        self.resetCache()

    def resetCache(self):
        self._glyphDrawings = [{}, {}]  # cache for (outline, colorLayers) objects
        self._currentVarLocation = None  # used to determine whether to purge the outline cache
        # Invalidate cached properties
        del self.unitsPerEm
        del self.colorPalettes
        del self.featuresGSUB
        del self.featuresGPOS
        del self.stylisticSetNames
        del self.scripts
        del self.axes

    def close(self):
        pass

    async def load(self, outputWriter):
        pass

    def updateFontPath(self, newFontPath):
        """This gets called when the source file was moved."""
        self.fontPath = newFontPath

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
        return None

    @cachedProperty
    def featuresGSUB(self):
        return set(self.shaper.getFeatures("GSUB"))

    @cachedProperty
    def featuresGPOS(self):
        return set(self.shaper.getFeatures("GPOS"))

    @cachedProperty
    def stylisticSetNames(self):
        return self.shaper.getStylisticSetNames()

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
                            maxValue=axis.maxValue,
                            hidden=bool(axis.flags & 0x0001))
            axes[axis.axisTag] = axisDict
        return axes

    @cachedProperty
    def instances(self):
        fvar = self.ttFont.get("fvar")
        if fvar is None:
            return []
        name = self.ttFont["name"]
        instances = []
        for i in fvar.instances:
            try:
                family_name = name.getBestFamilyName()
                if family_name is None:
                    # If not names are set (e.g. ds font) use same as font list
                    family_name = self.nameInCollection
                instance_name = name.getDebugName(i.subfamilyNameID)
                instances.append((f"{family_name} — {instance_name}", i.coordinates))
            except Exception as e:
                logging.error("Failed to parse instance name: %s" % str(e))
        return instances

    def getGlyphRunFromTextInfo(self, textInfo, colorPalettesIndex=0, **kwargs):
        text = textInfo.text
        direction = textInfo.directionOverride
        script = textInfo.scriptOverride
        language = textInfo.languageOverride

        if not self.colorPalettes:
            colorPalette = []
        else:
            colorPalette = self.colorPalettes[colorPalettesIndex]

        glyphs = GlyphsRun(len(text), self.unitsPerEm, direction in ("TTB", "BTT"), colorPalette)

        for segmentText, segmentScript, segmentBiDiLevel, firstCluster in textInfo.segments:
            if script is not None:
                segmentScript = script
            if direction is not None:
                segmentDirection = direction
            elif segmentBiDiLevel is None:
                segmentDirection = None  # Let HarfBuzz figure it out
            else:
                segmentDirection = ["LTR", "RTL"][segmentBiDiLevel % 2]
            run = self.getGlyphRun(segmentText,
                                   direction=segmentDirection,
                                   script=segmentScript,
                                   language=language,
                                   **kwargs)
            for gi in run:
                gi.cluster += firstCluster
            glyphs.extend(run)

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
        for glyph, glyphDrawing in zip(glyphInfo, self.getGlyphDrawings(glyphNames, colorLayers)):
            glyph.glyphDrawing = glyphDrawing
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

    def getGlyphDrawings(self, glyphNames, colorLayers=False):
        for glyphName in glyphNames:
            glyphDrawing = self._glyphDrawings[colorLayers].get(glyphName)
            if glyphDrawing is None:
                glyphDrawing = self._getGlyphDrawing(glyphName, colorLayers)
                self._glyphDrawings[colorLayers][glyphName] = glyphDrawing
            yield glyphDrawing

    def _purgeCaches(self):
        self._glyphDrawings = [{}, {}]

    def _getGlyphDrawing(self, glyphName, colorLayers):
        raise NotImplementedError()

    def varLocationChanged(self, varLocation):
        # Optional override
        pass


class GlyphsRun(list):

    def __init__(self, numChars, unitsPerEm, vertical, colorPalette=None):
        self.numChars = numChars
        self.unitsPerEm = unitsPerEm
        self.vertical = vertical
        self._glyphToChars = None
        self._charToGlyphs = None
        self.endPos = (0, 0)
        self.colorPalette = [] if colorPalette is None else colorPalette

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

    @cachedProperty
    def glyphNames(self):
        return [glyphInfo.name for glyphInfo in self]
