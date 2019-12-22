import io
from fontTools.misc.arrayTools import offsetRect
from fontTools.ttLib import TTFont
from ..misc.decorators import readOnlyCachedProperty
from ..misc.hbShape import HBShape
from ..misc.ftFont import FTFont
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
    def features(self):
        return sorted(set(self.shaper.getFeatures("GSUB") + self.shaper.getFeatures("GPOS")))

    @readOnlyCachedProperty
    def scripts(self):
        gsub = self.shaper.getScriptsAndLanguages("GSUB")
        gpos = self.shaper.getScriptsAndLanguages("GPOS")
        return mergeScriptsAndLanguages(gsub, gpos)

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

    def getGlyphRunFromTextInfo(self, textInfo, **kwargs):
        # TODO: move out mac-specific bounds code
        # TODO: write tests
        from ..mac.drawing import rectFromNSRect
        text = textInfo.text
        runLengths = textInfo.runLengths
        direction = textInfo.directionForShaper
        script = textInfo.scriptOverride
        language = textInfo.languageOverride

        glyphs = []
        index = 0
        for rl in runLengths:
            seg = text[index:index+rl]
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
            gi.pos = posX, posY = x + gi.dx, y + gi.dy
            if gi.path.elementCount():
                gi.bounds = offsetRect(rectFromNSRect(gi.path.controlPointBounds()), posX, posY)
            else:
                gi.bounds = None
            x += gi.ax
            y += gi.ay
        return glyphs, (x, y)


    def getGlyphRun(self, txt, *, features=None, variations=None,
                    direction=None, language=None, script=None,
                    colorLayers=False):
        glyphInfo = self.shape(txt, features=features, variations=variations,
                               direction=direction, language=language,
                               script=script)
        glyphNames = (gi.name for gi in glyphInfo)
        for glyph, path in zip(glyphInfo, self.getOutlinePaths(glyphNames, variations, colorLayers)):
            glyph.path = path
        return glyphInfo

    def shape(self, text, *, features, variations, direction, language, script):
        return self.shaper.shape(text, features=features, variations=variations,
                                 direction=direction, language=language, script=script)

    def getOutlinePaths(self, glyphNames, variations, colorLayers=False):
        if self._currentVarLocation != variations:
            # purge outline cache
            self._outlinePaths = [{}, {}]
            self._currentVarLocation = variations
        for glyphName in glyphNames:
            outline = self._outlinePaths[colorLayers].get(glyphName)
            if outline is None:
                outline = self._getOutlinePath(glyphName, colorLayers)
                self._outlinePaths[colorLayers][glyphName] = outline
            yield outline

    def _getOutlinePath(self, glyphName, colorLayers):
        raise NotImplementedError()


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
