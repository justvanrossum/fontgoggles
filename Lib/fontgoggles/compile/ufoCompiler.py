""" Tools to compile a UFO's features as quickly as possible."""

import logging
import pickle
import re
import sys
import traceback
from types import SimpleNamespace
import xml.etree.ElementTree as ET
from fontTools.feaLib.error import FeatureLibError
from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib import newTable
from fontTools.ufoLib import UFOReader
from fontTools.ufoLib.glifLib import _BaseParser as BaseGlifParser
from ufo2ft.featureCompiler import FeatureCompiler


def compileUFOToFont(ufoPath):
    """Compile the source UFO to a TTF with the smallest amount of tables
    needed to let HarfBuzz do its work. That would be 'cmap', 'post' and
    whatever OTL tables are needed for the features. Return the compiled
    font data.

    This function may do some redundant work (eg. we need an UFOReader
    elsewhere, too), but having a picklable argument and return value
    allows us to run it in a separate process, enabling parallelism.
    """
    reader = UFOReader(ufoPath, validate=False)
    ufo2 = reader.formatVersionTuple[0] < 3
    glyphSet = reader.getGlyphSet()
    info = SimpleNamespace()
    reader.readInfo(info)

    glyphOrder = sorted(glyphSet.keys())  # no need for the "real" glyph order
    if ".notdef" not in glyphOrder:
        # We need a .notdef glyph, so let's make one.
        glyphOrder.insert(0, ".notdef")
    widths, cmap, revCmap, anchors = fetchGlyphInfo(glyphSet, ufoPath, ufo2=ufo2)
    fb = FontBuilder(round(info.unitsPerEm))
    fb.setupGlyphOrder(glyphOrder)
    fb.setupCharacterMap(cmap)
    fb.setupPost()  # This makes sure we store the glyph names
    ttFont = fb.font
    # Store anchors in the font as a private table: this is valuable
    # data that our parent process can use to do faster reloading upon
    # changes.
    ttFont["FGAx"] = newTable("FGAx")
    ttFont["FGAx"].data = pickle.dumps(anchors)
    ufo = MinimalFontObject(ufoPath, reader, widths, revCmap, anchors)
    feaComp = FeatureCompiler(ufo, ttFont)
    try:
        feaComp.compile()
    except FeatureLibError as e:
        error = f"{e.__class__.__name__}: {e}"
    except Exception:
        # This is most likely a bug, and not an input error, so perhaps
        # we shouldn't even catch it here.
        error = traceback.format_exc()
    else:
        error = None
    return ttFont, error


def compileUFOToPath(ufoPath, ttPath):
    ttFont, error = compileUFOToFont(ufoPath)
    if error:
        print(error, file=sys.stderr)
    ttFont.save(ttPath, reorderTables=False)


_tagGLIFPattern = re.compile(rb"(<\s*(advance|anchor|unicode)\s+([^>]+)>)")
_ufo2AnchorPattern = re.compile(
    rb"<contour>\s+(<point\s+[^>]+move[^>]+name[^>]+>)\s+</contour>"
)
_unicodeAttributeGLIFPattern = re.compile(rb"hex\s*=\s*\"([0-9A-Fa-f]+)\"")
_widthAttributeGLIFPattern = re.compile(rb"width\s*=\s*\"([0-9A-Fa-f]+)\"")


def fetchGlyphInfo(glyphSet, ufoPath, glyphNames=None, ufo2=False):
    # This seems about 2.3 times faster than reader.getCharacterMapping()
    widths = {}
    cmap = {}  # unicode: glyphName
    revCmap = {}
    anchors = {}  # glyphName: [(anchorName, x, y), ...]
    duplicateUnicodes = {}
    if glyphNames is None:
        glyphNames = sorted(glyphSet.keys())
    for glyphName in glyphNames:
        data = glyphSet.getGLIF(glyphName)
        if b"<!--" in data:
            # Fall back to proper parser, assuming this to be uncommon
            # (This does not work for UFO 2)
            width, unicodes, glyphAnchors = fetchUnicodesAndAnchors(data)
        else:
            # Fast route with regex
            width = None
            unicodes = []
            glyphAnchors = []
            for rawElement, tag, rawAttributes in _tagGLIFPattern.findall(data):
                if tag == b"unicode":
                    m = _unicodeAttributeGLIFPattern.match(rawAttributes)
                    try:
                        unicodes.append(int(m.group(1), 16))
                    except ValueError:
                        pass
                elif tag == b"anchor":
                    root = ET.fromstring(rawElement)
                    glyphAnchors.append(_parseAnchorAttrs(root.attrib))
                elif tag == b"advance":
                    m = _widthAttributeGLIFPattern.search(rawAttributes)
                    if m is not None:
                        width = float(m.group(1))
            if ufo2:
                for rawElement in _ufo2AnchorPattern.findall(data):
                    root = ET.fromstring(rawElement)
                    glyphAnchors.append(_parseAnchorAttrs(root.attrib))

        widths[glyphName] = width

        uniqueUnicodes = []
        for codePoint in unicodes:
            if codePoint not in cmap:
                cmap[codePoint] = glyphName
                uniqueUnicodes.append(codePoint)
            else:
                if codePoint in duplicateUnicodes:
                    duplicateUnicodes[codePoint].append(glyphName)
                else:
                    duplicateUnicodes[codePoint] = [cmap[codePoint], glyphName]
        if glyphAnchors:
            anchors[glyphName] = glyphAnchors
        if uniqueUnicodes:
            revCmap[glyphName] = uniqueUnicodes

    if duplicateUnicodes:
        dupMessage = "; ".join(
            f"U+{codePoint:04X}:{','.join(glyphNames)}"
            for codePoint, glyphNames in sorted(duplicateUnicodes.items())
        )
        logger = logging.getLogger("fontgoggles.font.ufoFont")
        logger.warning(
            "Some code points in '%s' are assigned to multiple glyphs: %s",
            ufoPath,
            dupMessage,
        )
    return widths, cmap, revCmap, anchors


def fetchUnicodesAndAnchors(glif):
    """
    Get a list of unicodes listed in glif.
    """
    parser = FetchUnicodesAndAnchorsParser()
    parser.parse(glif)
    return parser.advanceWidth, parser.unicodes, parser.anchors


def _parseNumber(s):
    if not s:
        return None
    f = float(s)
    i = int(f)
    if i == f:
        return i
    return f


def _parseAnchorAttrs(attrs):
    return (
        attrs.get("name"),
        _parseNumber(attrs.get("x")),
        _parseNumber(attrs.get("y")),
        attrs.get("identifier"),
    )


class FetchUnicodesAndAnchorsParser(BaseGlifParser):

    def __init__(self):
        self.unicodes = []
        self.anchors = []
        self.advanceWidth = None
        super().__init__()

    def startElementHandler(self, name, attrs):
        if self._elementStack and self._elementStack[-1] == "glyph":
            if name == "unicode":
                value = attrs.get("hex")
                if value is not None:
                    try:
                        value = int(value, 16)
                        if value not in self.unicodes:
                            self.unicodes.append(value)
                    except ValueError:
                        pass
            elif name == "anchor":
                self.anchors.append(_parseAnchorAttrs(attrs))
            elif name == "advance":
                self.advanceWidth = _parseNumber(attrs.get("width"))
        super().startElementHandler(name, attrs)


class MinimalFontObject:

    # This class and its relatives implement a defcon-like font object, but
    # only support the bare minimum for ufo2ft's FeatureCompiler to do its
    # work. No outlines are needed, no advances, no glyph.lib, only glyph
    # unicodes and anchors, and at the font level, only features, groups,
    # kerning and lib are needed.

    def __init__(self, ufoPath, reader, widths, revCmap, anchors):
        self.path = ufoPath
        self._widths = widths
        self._revCmap = revCmap
        self._anchors = anchors
        self._glyphNames = set(reader.getGlyphSet().contents.keys())
        self._glyphNames.add(".notdef")  # ensure we have .notdef
        self.features = MinimalFeaturesObject(reader.readFeatures())
        self.groups = reader.readGroups()
        self.kerning = reader.readKerning()
        self.lib = reader.readLib()
        self.info = SimpleNamespace()
        reader.readInfo(self.info)
        self._glyphs = {}

    def keys(self):
        return self._glyphNames

    def __iter__(self):
        for glyphName in self._glyphNames:
            glyph = self[glyphName]
            yield glyph

    def __getitem__(self, glyphName):
        if glyphName not in self._glyphNames:
            raise KeyError(glyphName)
        # TODO: should we even bother caching?
        glyph = self._glyphs.get(glyphName)
        if glyph is None:
            glyph = MinimalGlyphObject(
                glyphName,
                self._widths.get(glyphName, 0),
                self._revCmap.get(glyphName),
                self._anchors.get(glyphName, ()),
            )
            self._glyphs[glyphName] = glyph
        return glyph


class MinimalGlyphObject:

    def __init__(self, name, width, unicodes, anchors):
        self.name = name
        self.width = width
        self.unicodes = unicodes
        self.anchors = [
            MinimalAnchorObject(name, x, y, identifier)
            for name, x, y, identifier in anchors
        ]

    @property
    def unicode(self):
        return self.unicodes[0] if self.unicodes else None


class MinimalAnchorObject:

    def __init__(self, name, x, y, identifier):
        self.name = name
        self.x = x
        self.y = y
        self.identifier = identifier


class MinimalFeaturesObject:

    def __init__(self, featureText):
        self.text = featureText
