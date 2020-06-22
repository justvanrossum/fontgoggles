from collections import defaultdict
import functools
import io
import itertools
from fontTools.ttLib import TTFont
import uharfbuzz as hb


class GlyphInfo:

    def __init__(self, gid, name, cluster, dx, dy, ax, ay):
        self.gid = gid
        self.name = name
        self.cluster = cluster
        self.dx = dx
        self.dy = dy
        self.ax = ax
        self.ay = ay

    def __repr__(self):
        args = (f"{a}={repr(getattr(self, a))}"
                for a in ["gid", "name", "cluster", "dx", "dy", "ax", "ay"])
        return f"{self.__class__.__name__}({', '.join(args)})"


#
# To generalize, HB needs
# - a callback to map a character to a glyph ID
# - a callback to get the advance width for a glyph ID
# - a callback to get the advance height for a glyph ID
# - either data for a minimal ttf, or a callback getting individual table data
#   (the latter is broken in current uharfbuzz)
# To make our shaper work, we need
# - to provide a glyph order so we can map glyph IDs to glyph names
# - apart from providing a glyph order, we want our callbacks to deal
#   with glyph names, not glyph IDs.
#


def _getGlyphIDFunc(font, char, shaper):
    glyphName = shaper.getGlyphNameFromCodePoint(char)
    if glyphName is None:
        return 0  # .notdef
    glyphID = shaper.getGlyphID(glyphName, 0)
    return glyphID


def _getHorizontalAdvanceFunc(font, glyphID, shaper):
    glyphName = shaper.glyphOrder[glyphID]
    return shaper.getHorizontalAdvance(glyphName)


def _getVerticalAdvanceFunc(font, glyphID, shaper):
    glyphName = shaper.glyphOrder[glyphID]
    return shaper.getVerticalAdvance(glyphName)


def _getVerticalOriginFunc(font, glyphID, shaper):
    glyphName = shaper.glyphOrder[glyphID]
    return shaper.getVerticalOrigin(glyphName)


_stylisticSets = {f"ss{i:02}" for i in range(1, 21)}


class HBShape:

    @classmethod
    def fromPath(cls, path, **kwargs):
        with open(path, "rb") as f:
            fontData = f.read()
        return cls(fontData, **kwargs)

    def __init__(self, fontData, *, fontNumber=0,
                 getGlyphNameFromCodePoint=None,
                 getHorizontalAdvance=None,
                 getVerticalAdvance=None,
                 getVerticalOrigin=None,
                 ttFont=None):
        self._fontData = fontData
        self._fontNumber = fontNumber
        self.face = hb.Face(fontData, fontNumber)
        self.font = hb.Font(self.face)

        if ttFont is None:
            f = io.BytesIO(self._fontData)
            ttFont = TTFont(f, fontNumber=self._fontNumber, lazy=True)
        self._ttFont = ttFont
        self.glyphOrder = ttFont.getGlyphOrder()

        if getGlyphNameFromCodePoint is None and getHorizontalAdvance is not None:
            def _getGlyphNameFromCodePoint(cmap, codePoint):
                return cmap.get(codePoint)
            getGlyphNameFromCodePoint = functools.partial(_getGlyphNameFromCodePoint, self._ttFont.getBestCmap())

        if getGlyphNameFromCodePoint is not None:
            assert getHorizontalAdvance is not None

        self.getGlyphNameFromCodePoint = getGlyphNameFromCodePoint
        self.getHorizontalAdvance = getHorizontalAdvance
        self.getVerticalAdvance = getVerticalAdvance
        self.getVerticalOrigin = getVerticalOrigin

        if getGlyphNameFromCodePoint is not None and getHorizontalAdvance is not None:
            self._funcs = hb.FontFuncs.create()
            self._funcs.set_nominal_glyph_func(_getGlyphIDFunc, self)
            self._funcs.set_glyph_h_advance_func(_getHorizontalAdvanceFunc, self)
            if getVerticalAdvance is not None:
                self._funcs.set_glyph_v_advance_func(_getVerticalAdvanceFunc, self)
            if getVerticalOrigin is not None:
                self._funcs.set_glyph_v_origin_func(_getVerticalOriginFunc, self)
        else:
            self._funcs = None

    def getFeatures(self, otTableTag):
        features = set()
        for scriptIndex, script in enumerate(hb.ot_layout_table_get_script_tags(self.face, otTableTag)):
            langIdices = list(range(len(hb.ot_layout_script_get_language_tags(self.face, otTableTag, scriptIndex))))
            langIdices.append(0xFFFF)
            for langIndex in langIdices:
                features.update(hb.ot_layout_language_get_feature_tags(self.face, otTableTag, scriptIndex, langIndex))
        return features

    def getStylisticSetNames(self):
        tags = _stylisticSets & set(self.getFeatures("GSUB"))
        if not tags:
            return {}
        gsubTable = self._ttFont.get("GSUB")
        nameTable = self._ttFont.get("name")
        if gsubTable is None or nameTable is None:
            return {}
        gsubTable = gsubTable.table
        names = {}
        for feature in gsubTable.FeatureList.FeatureRecord:
            tag = feature.FeatureTag
            if tag in tags and tag not in names:
                feaParams = feature.Feature.FeatureParams
                if feaParams is not None:
                    nameRecord = nameTable.getName(feaParams.UINameID, 3, 1)
                    if nameRecord is not None:
                        names[tag] = nameRecord.toUnicode()
        return names

    def getScriptsAndLanguages(self, otTableTag):
        scriptsAndLanguages = {}
        for scriptIndex, script in enumerate(hb.ot_layout_table_get_script_tags(self.face, otTableTag)):
            scriptsAndLanguages[script] = set(hb.ot_layout_script_get_language_tags(self.face, otTableTag, scriptIndex))
        return scriptsAndLanguages

    def getGlyphID(self, glyphName, default=0):
        try:
            return self._ttFont.getGlyphID(glyphName)
        except KeyError:
            return default

    def shape(self, text, *, features=None, varLocation=None,
              direction=None, language=None, script=None):
        if features is None:
            features = {}
        if varLocation is None:
            varLocation = {}

        self.font.scale = (self.face.upem, self.face.upem)
        self.font.set_variations(varLocation)

        hb.ot_font_set_funcs(self.font)

        if self._funcs is not None:
            self.font.funcs = self._funcs

        buf = hb.Buffer.create()
        buf.add_str(str(text))  # add_str() does not accept str subclasses
        buf.guess_segment_properties()

        buf.cluster_level = hb.BufferClusterLevel.MONOTONE_CHARACTERS

        if direction is not None:
            buf.direction = direction
        if language is not None:
            buf.set_language_from_ot_tag(language)
        if script is not None:
            buf.set_script_from_ot_tag(script)

        hb.shape(self.font, buf, features)

        glyphOrder = self.glyphOrder
        infos = []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            infos.append(GlyphInfo(info.codepoint, glyphOrder[info.codepoint], info.cluster, *pos.position))

        return infos


def characterGlyphMapping(clusters, numChars):
    """This implements character to glyph mapping and vice versa, using
    cluster information from HarfBuzz. It should be correct for HB
    clustering support levels 0 and 1, see:

        https://harfbuzz.github.io/working-with-harfbuzz-clusters.html

    "Each character belongs to the cluster that has the highest cluster
    value not larger than its initial cluster value.""
    """

    if clusters:
        if clusters[-1] != 0:
            assert clusters[0] == 0

    clusterToChars = {}
    charToCluster = {}
    for cl, clNext in _pairs(sorted(set(clusters)), numChars):
        chars = list(range(cl, clNext))
        clusterToChars[cl] = chars
        for char in chars:
            charToCluster[char] = cl

    glyphToChars = [clusterToChars[cl] for cl in clusters]

    charToGlyphs = defaultdict(list)
    for glyphIndex, charIndices in enumerate(glyphToChars):
        for ci in charIndices:
            charToGlyphs[ci].append(glyphIndex)

    # assert sorted(charToGlyphs) == list(range(numChars)), charToGlyphs
    charToGlyphs = [charToGlyphs[ci] for ci in sorted(charToGlyphs)]

    return glyphToChars, charToGlyphs


def _pairs(seq, sentinel):
    it = itertools.chain(seq, (sentinel,))
    prev = next(it)
    for i in it:
        yield prev, i
        prev = i
