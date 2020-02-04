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
from fontTools.ufoLib import (DEFAULT_GLYPHS_DIRNAME, FONTINFO_FILENAME, GROUPS_FILENAME,
                              KERNING_FILENAME, FEATURES_FILENAME)
from fontTools.ufoLib.glifLib import Glyph as GLIFGlyph, CONTENTS_FILENAME
from .baseFont import BaseFont
from ..misc.compilerPool import compileUFOToBytes
from ..misc.hbShape import HBShape
from ..misc.properties import cachedProperty
from ..misc.ufoCompiler import fetchCharacterMappingAndAnchors


ufoFilesToTrack = [FONTINFO_FILENAME, GROUPS_FILENAME, KERNING_FILENAME, FEATURES_FILENAME]


class UFOFont(BaseFont):

    glyphModTimes = None
    anchors = None
    revCmap = None

    def _setupReaderAndGlyphSet(self):
        self.reader = UFOReader(self.fontPath, validate=False)
        self.glyphSet = self.reader.getGlyphSet()
        self.glyphSet.glyphClass = Glyph

    def updateFontPath(self, newFontPath):
        """This gets called when the source file was moved."""
        super().updateFontPath(newFontPath)
        self._setupReaderAndGlyphSet()

    def canReloadWithChange(self, externalFilePath):
        if self.reader.fileStructure != UFOFileStructure.PACKAGE:
            # We can't (won't) partially reloadToTrack .ufoz
            return False
        if externalFilePath:
            # Features need to be recompiled no matter what
            return False
        # TODO: much of this logic needs to be factored out so it can be shared
        # with DSFont, which does not use UFOFont for its sources.
        self.glyphSet.rebuildContents()
        glyphModTimes, contentsModTime = getGlyphModTimes(self.glyphSet)
        if glyphModTimes != self.glyphModTimes or contentsModTime != self.contentsModTime:
            changedGlyphNames = {glyphName for glyphName, mtime in glyphModTimes ^ self.glyphModTimes}
            deletedGlyphNames = {glyphName for glyphName in changedGlyphNames if glyphName not in self.glyphSet}
            changedGlyphNames -= deletedGlyphNames
            _, changedRevCmap, changedAnchors = fetchCharacterMappingAndAnchors(self.glyphSet, self.fontPath, changedGlyphNames)
            if self.anchors is None:
                prevAnchors = pickle.loads(self.ttFont["FGAx"].data)
            else:
                prevAnchors = self.anchors

            for gn in prevAnchors:
                if gn in changedGlyphNames and gn not in changedAnchors:
                    changedAnchors[gn] = []  # Anchor(s) got deleted

            currentAnchors = {gn: anchors for gn, anchors in prevAnchors.items()
                              if gn not in deletedGlyphNames}
            currentAnchors.update(changedAnchors)
            if prevAnchors != currentAnchors:
                return False

            # Look for cmap changes
            if self.revCmap is None:
                prevCmap = self.ttFont.getBestCmap()
                prevRevCmap = defaultdict(list)
                for code, gn in prevCmap.items():
                    prevRevCmap[gn].append(code)
            else:
                prevRevCmap = self.revCmap

            for gn in prevRevCmap:
                if gn in changedGlyphNames and gn not in changedRevCmap:
                    changedRevCmap[gn] = []  # Unicode got deleted

            currentRevCmap = {gn: codes for gn, codes in prevRevCmap.items()
                              if gn not in deletedGlyphNames}
            currentRevCmap.update(changedRevCmap)

            if prevRevCmap != currentRevCmap:
                # The cmap changed. Let's update it in-place and only rebuild the shaper
                cmap = {code: gn for gn, codes in currentRevCmap.items() for code in codes}
                del self.ttFont["cmap"]
                fb = FontBuilder(font=self.ttFont)
                fb.setupCharacterMap(cmap)
                f = io.BytesIO()
                self.ttFont.save(f, reorderTables=False)
                fontData = f.getvalue()
                self.shaper = self._getShaper(fontData)
                self.revCmap = currentRevCmap

            self.glyphModTimes = glyphModTimes
            self.contentsModTime = contentsModTime
            self.resetCache()
            return True

        fileModTimes = getFileModTimes(self.reader.fs.getsyspath("/"), ufoFilesToTrack)
        changedFiles = {fileName for fileName, modTime in fileModTimes ^ self.fileModTimes}
        self.fileModTimes = fileModTimes
        if FEATURES_FILENAME in changedFiles or GROUPS_FILENAME in changedFiles or KERNING_FILENAME in changedFiles:
            return False
        if FONTINFO_FILENAME in changedFiles:
            # Only interesting for a potentially changed unitsPerEm
            self.info = SimpleNamespace()
            self.reader.readInfo(self.info)
            self.resetCache()
            return True

        # Nothing changed that we know of or care about (eg. lib.plist)
        return True

    async def load(self, outputWriter):
        if hasattr(self, "reader"):
            self._cachedGlyphs = {}
            return
        self._setupReaderAndGlyphSet()
        self.info = SimpleNamespace()
        self.reader.readInfo(self.info)
        self._cachedGlyphs = {}
        if self.glyphModTimes is None:
            self.glyphModTimes, self.contentsModTime = getGlyphModTimes(self.glyphSet)
            self.fileModTimes = getFileModTimes(self.reader.fs.getsyspath("/"), ufoFilesToTrack)

        fontData = await compileUFOToBytes(self.fontPath, outputWriter)

        self._includedFeatureFiles = extractIncludedFeatureFiles(self.fontPath, self.reader)

        f = io.BytesIO(fontData)
        self.ttFont = TTFont(f, lazy=True)
        self.shaper = self._getShaper(fontData)

    def _getShaper(self, fontData):
        return HBShape(fontData,
                       getHorizontalAdvance=self._getHorizontalAdvance,
                       getVerticalAdvance=self._getVerticalAdvance,
                       getVerticalOrigin=self._getVerticalOrigin,
                       ttFont=self.ttFont)

    def getExternalFiles(self):
        return self._includedFeatureFiles

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

    def _getOutlinePath(self, glyphName, colorLayers):
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
