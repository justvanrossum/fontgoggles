from collections import defaultdict
import io
import pathlib
import pickle
import os
import re
import sys
from types import SimpleNamespace
from fontTools.feaLib.parser import Parser as FeatureParser
from fontTools.feaLib.ast import IncludeStatement
from fontTools.feaLib.error import FeatureLibError
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.cocoaPen import CocoaPen  # TODO: factor out mac-specific code
from fontTools.ttLib import TTFont
from fontTools.ufoLib import UFOReader, UFOFileStructure
from fontTools.ufoLib import FONTINFO_FILENAME, GROUPS_FILENAME, KERNING_FILENAME, FEATURES_FILENAME
from fontTools.ufoLib.glifLib import Glyph as GLIFGlyph, CONTENTS_FILENAME
from .baseFont import BaseFont
from ..compile.compilerPool import compileUFOToBytes
from ..compile.ufoCompiler import fetchCharacterMappingAndAnchors
from ..misc.hbShape import HBShape
from ..misc.properties import cachedProperty


class UFOFont(BaseFont):

    ufoState = None

    def _setupReaderAndGlyphSet(self):
        self.reader = UFOReader(self.fontPath, validate=False)
        self.glyphSet = self.reader.getGlyphSet()
        self.glyphSet.glyphClass = Glyph

    async def load(self, outputWriter):
        if hasattr(self, "reader"):
            self._cachedGlyphs = {}
            return
        self._setupReaderAndGlyphSet()
        self.info = SimpleNamespace()
        self.reader.readInfo(self.info)
        self._cachedGlyphs = {}
        if self.ufoState is None:
            includedFeatureFiles = extractIncludedFeatureFiles(self.fontPath, self.reader)
            self.ufoState = UFOState(self.reader, self.glyphSet,
                                     getUnicodesAndAnchors=self._getUnicodesAndAnchors,
                                     includedFeatureFiles=includedFeatureFiles)

        fontData = await compileUFOToBytes(self.fontPath, outputWriter)

        f = io.BytesIO(fontData)
        self.ttFont = TTFont(f, lazy=True)
        self.shaper = self._getShaper(fontData)

    def updateFontPath(self, newFontPath):
        """This gets called when the source file was moved."""
        super().updateFontPath(newFontPath)
        self._setupReaderAndGlyphSet()

    def getExternalFiles(self):
        return self.ufoState.includedFeatureFiles

    def canReloadWithChange(self, externalFilePath):
        if self.reader.fileStructure != UFOFileStructure.PACKAGE:
            # We can't (won't) partially reload .ufoz
            return False

        if externalFilePath:
            # Features need to be recompiled no matter what
            return False

        self.glyphSet.rebuildContents()

        self.ufoState = self.ufoState.newState()
        needsFeaturesUpdate, needsGlyphUpdate, needsInfoUpdate, needsCmapUpdate = self.ufoState.getUpdateInfo()

        if needsFeaturesUpdate:
            return False

        if needsInfoUpdate:
            # font.info changed, all we care about is a possibly change unitsPerEm
            self.info = SimpleNamespace()
            self.reader.readInfo(self.info)

        if needsCmapUpdate:
            # The cmap changed. Let's update it in-place and only rebuild the shaper
            newCmap = {code: gn for gn, codes in self.ufoState.unicodes.items() for code in codes}
            fb = FontBuilder(font=self.ttFont)
            fb.setupCharacterMap(newCmap)
            f = io.BytesIO()
            self.ttFont.save(f, reorderTables=False)
            self.shaper = self._getShaper(f.getvalue())

        if needsGlyphUpdate or needsInfoUpdate or needsCmapUpdate:
            self.resetCache()

        return True

    def _getUnicodesAndAnchors(self):
        unicodes = defaultdict(list)
        for code, gn in self.ttFont.getBestCmap().items():
            unicodes[gn].append(code)
        anchors = pickle.loads(self.ttFont["FGAx"].data)
        return unicodes, anchors

    def _getShaper(self, fontData):
        return HBShape(fontData,
                       getHorizontalAdvance=self._getHorizontalAdvance,
                       getVerticalAdvance=self._getVerticalAdvance,
                       getVerticalOrigin=self._getVerticalOrigin,
                       ttFont=self.ttFont)

    @cachedProperty
    def unitsPerEm(self):
        return self.info.unitsPerEm

    def _getGlyph(self, glyphName):
        glyph = self._cachedGlyphs.get(glyphName)
        if glyph is None:
            if glyphName == ".notdef" and glyphName not in self.glyphSet:
                # We need a .notdef glyph, so let's make one.
                glyph = NotDefGlyph(self.info.unitsPerEm)
                self._addOutlinePathToGlyph(glyph)
            else:
                try:
                    glyph = self.glyphSet[glyphName]
                    self._addOutlinePathToGlyph(glyph)
                except Exception as e:
                    # TODO: logging would be better but then capturing in mainWindow.py is harder
                    print(f"Glyph '{glyphName}' could not be read: {e!r}", file=sys.stderr)
                    glyph = self._getGlyph(".notdef")
            self._cachedGlyphs[glyphName] = glyph
        return glyph

    def _addOutlinePathToGlyph(self, glyph):
        pen = CocoaPen(self.glyphSet)
        glyph.draw(pen)
        glyph.outline = pen.path

    def _getHorizontalAdvance(self, glyphName):
        glyph = self._getGlyph(glyphName)
        return glyph.width

    @cachedProperty
    def defaultVerticalAdvance(self):
        ascender = getattr(self.info, "ascender", None)
        descender = getattr(self.info, "descender", None)
        if ascender is None or descender is None:
            return self.info.unitsPerEm
        else:
            return ascender + abs(descender)

    @cachedProperty
    def defaultVerticalOriginY(self):
        ascender = getattr(self.info, "ascender", None)
        if ascender is None:
            return self.info.unitsPerEm  # ???
        else:
            return ascender

    def _getVerticalAdvance(self, glyphName):
        glyph = self._getGlyph(glyphName)
        vAdvance = glyph.height
        if vAdvance is None or vAdvance == 0:  # XXX default vAdv == 0 -> bad UFO spec
            vAdvance = self.defaultVerticalAdvance
        return -abs(vAdvance)

    def _getVerticalOrigin(self, glyphName):
        glyph = self._getGlyph(glyphName)
        vOrgX = glyph.width / 2
        lib = getattr(glyph, "lib", {})
        vOrgY = lib.get("public.verticalOrigin")
        if vOrgY is None:
            vOrgY = self.defaultVerticalOriginY
        return True, vOrgX, vOrgY

    def _getGlyphDrawing(self, glyphName, colorLayers):
        glyph = self._getGlyph(glyphName)
        return glyph.outline


class NotDefGlyph:

    def __init__(self, unitsPerEm):
        self.unitsPerEm = unitsPerEm
        self.width = unitsPerEm // 2
        self.height = unitsPerEm

    def draw(self, pen):
        inset = 0.05 * self.unitsPerEm
        sideBearing = 0.05 * self.unitsPerEm
        height = 0.75 * self.unitsPerEm
        xMin, yMin, xMax, yMax = sideBearing, 0, self.width - sideBearing, height
        pen.moveTo((xMin, yMin))
        pen.lineTo((xMin, yMax))
        pen.lineTo((xMax, yMax))
        pen.lineTo((xMax, yMin))
        pen.closePath()
        xMin += inset
        yMin += inset
        xMax -= inset
        yMax -= inset
        pen.moveTo((xMin, yMin))
        pen.lineTo((xMax, yMin))
        pen.lineTo((xMax, yMax))
        pen.lineTo((xMin, yMax))
        pen.closePath()

    def setVarLocation(self, varLocation):
        # For compatibility with dsFont.VarGlyph
        pass

    def getOutline(self):
        pen = CocoaPen(None)  # by now there are no more composites
        self.draw(pen)
        return pen.path


class Glyph(GLIFGlyph):
    width = 0
    height = None


def extractIncludedFeatureFiles(ufoPath, reader=None):
    if isinstance(ufoPath, str):
        ufoPath = pathlib.Path(ufoPath)
    if reader is None:
        reader = UFOReader(ufoPath, validate=False)
    mainFeatures = reader.readFeatures()
    if not mainFeatures:
        return ()
    return sorted(set(_extractIncludedFeatureFiles(mainFeatures, [ufoPath.parent])))


def _extractIncludedFeatureFiles(featureSource, searchPaths, recursionLevel=0):
    if recursionLevel > 50:
        raise FeatureLibError("Too many recursive includes", None)
    for fileName in _parseFeaSource(featureSource):
        for d in searchPaths:
            p = d / fileName
            if p.exists():
                p = p.resolve()
                yield p
                yield from _extractIncludedFeatureFiles(p.read_text("utf-8", "replace"),
                                                        [searchPaths[0], p.parent],
                                                        recursionLevel+1)
                break


_feaIncludePat = re.compile(r"include\s*\(([^)]+)\)")


def _parseFeaSource(featureSource):
    pos = 0
    while True:
        m = _feaIncludePat.search(featureSource, pos)
        if m is None:
            break
        pos = m.end()

        lineStart = featureSource.rfind("\n", 0, m.start())
        lineEnd = featureSource.find("\n", m.end())
        if lineStart == -1:
            lineStart = 0
        if lineEnd == -1:
            lineEnd = len(featureSource)
        line = featureSource[lineStart:lineEnd]
        f = io.StringIO(line)
        p = FeatureParser(f, followIncludes=False)
        for st in p.parse().statements:
            if isinstance(st, IncludeStatement):
                yield st.filename


ufoFilesToTrack = [FONTINFO_FILENAME, GROUPS_FILENAME, KERNING_FILENAME, FEATURES_FILENAME]


class UFOState:

    """Object to keep track of various file modification times and miscellaneous
    other state needed to determine how to handle reloading of the UFO data. Sometimes
    features need to be rebuilt, other times an outline cache flush is enough.
    """

    #
    # This is rather intricate as we try to do as little work as possible.
    # For example, the first time a UFO is loaded, all .glif files are parsed
    # to collect anchor information (needed for mark features) and unicodes
    # (to build the cmap). Upon external changes to the UFO, we don't want to
    # redo all that work (it wouldn't scale to large UFOs) so we keep track
    # of the anchors and unicodes by only reparsing .glif files that actually
    # changed.
    #
    # This does _not_ track changes to included .fea files. That part is handled
    # by UFOFont.canReloadWithChange() as we'll get separate file-changed events
    # for that.
    #

    def __init__(self, reader, glyphSet, anchors=None, unicodes=None,
                 getUnicodesAndAnchors=None, includedFeatureFiles=(),
                 previousState=None):
        self.reader = reader
        self.glyphSet = glyphSet
        assert (anchors is not None) == (getUnicodesAndAnchors is None)
        assert (unicodes is not None) == (getUnicodesAndAnchors is None)
        self._anchors = anchors
        self._unicodes = unicodes
        self._getUnicodesAndAnchors = getUnicodesAndAnchors
        self.glyphModTimes, self.contentsModTime = getGlyphModTimes(glyphSet)
        self.fileModTimes = getFileModTimes(reader.fs.getsyspath("/"), ufoFilesToTrack)
        self.includedFeatureFiles = includedFeatureFiles
        self._previousState = previousState

    def newState(self):
        # This method can only be called on a brand new state without a previous
        # state, or on a state that was properly updated via a call to getUpdateInfo()
        assert self._previousState is None, "state was not updated"
        newState = UFOState(self.reader, self.glyphSet,
                            self._anchors, self._unicodes,
                            self._getUnicodesAndAnchors,
                            self.includedFeatureFiles,
                            self)
        self._previousState = None
        return newState

    def getUpdateInfo(self):
        # Calling this method has the side effect of updating the internal state
        # to the current state of the UFO.
        prev = self._previousState
        assert prev is not None, "getUpdateInfo() is a one-shot method"  # Or: memoize
        self._previousState = None

        changedFiles = {fileName for fileName, modTime in prev.fileModTimes ^ self.fileModTimes}

        needsInfoUpdate = FONTINFO_FILENAME in changedFiles

        needsFeaturesUpdate = (FEATURES_FILENAME in changedFiles or
                               GROUPS_FILENAME in changedFiles or
                               KERNING_FILENAME in changedFiles)

        needsGlyphUpdate = False
        needsCmapUpdate = False

        if prev.glyphModTimes != self.glyphModTimes or prev.contentsModTime != self.contentsModTime:
            changedGlyphNames = {glyphName for glyphName, mtime in prev.glyphModTimes ^ self.glyphModTimes}
            deletedGlyphNames = {glyphName for glyphName in changedGlyphNames if glyphName not in self.glyphSet}

            _, changedUnicodes, changedAnchors = fetchCharacterMappingAndAnchors(self.glyphSet,
                                                                                 self.reader.fs.getsyspath("/"),
                                                                                 changedGlyphNames - deletedGlyphNames)

            # Within the changed glyphs, let's see if their anchors changed
            for gn in changedGlyphNames:
                if gn in prev.anchors and gn not in changedAnchors:
                    changedAnchors[gn] = []  # Anchor(s) got deleted

            anchors = dict(prev.anchors)
            anchors.update(changedAnchors)
            self.anchors = {gn: anchorList for gn, anchorList in anchors.items() if anchorList}
            needsFeaturesUpdate = prev.anchors != self.anchors

            # Within the changed glyphs, let's see if their unicodes changed
            for gn in changedGlyphNames:
                if gn in prev.unicodes and gn not in changedUnicodes:
                    changedUnicodes[gn] = []  # Unicode(s) got deleted

            unicodes = dict(prev.unicodes)
            unicodes.update(changedUnicodes)
            self.unicodes = {gn: codes for gn, codes in unicodes.items() if codes}
            needsCmapUpdate = prev.unicodes != self.unicodes
            needsGlyphUpdate = bool(changedGlyphNames)

        return needsFeaturesUpdate, needsGlyphUpdate, needsInfoUpdate, needsCmapUpdate

    @property
    def anchors(self):
        if self._anchors is None:
            self._unicodes, self._anchors = self._getUnicodesAndAnchors()
            self._getUnicodesAndAnchors = None
        return self._anchors

    @anchors.setter
    def anchors(self, anchors):
        self._anchors = anchors
        self._getUnicodesAndAnchors = None

    @property
    def unicodes(self):
        if self._unicodes is None:
            self._unicodes, self._anchors = self._getUnicodesAndAnchors()
            self._getUnicodesAndAnchors = None
        return self._unicodes

    @unicodes.setter
    def unicodes(self, unicodes):
        self._unicodes = unicodes
        self._getUnicodesAndAnchors = None


def getModTime(path):
    try:
        return os.stat(path).st_mtime
    except FileNotFoundError:
        return None


def getGlyphModTimes(glyphSet):
    folder = glyphSet.fs.getsyspath("/")  # We don't support .ufoz here
    contentsModTime = getModTime(os.path.join(folder, CONTENTS_FILENAME))
    return {(glyphName, getModTime(os.path.join(folder, fileName)))
            for glyphName, fileName in glyphSet.contents.items()}, contentsModTime


def getFileModTimes(folder, fileNames):
    return {(fileName, getModTime(os.path.join(folder, fileName)))
            for fileName in fileNames}


if __name__ == "__main__":
    for feaPath in extractIncludedFeatureFiles(sys.argv[1]):
        print(feaPath)
