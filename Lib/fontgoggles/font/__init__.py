from os import PathLike
from types import SimpleNamespace


def getOpener(fontPath: PathLike):
    openerKey = sniffFontType(fontPath)
    assert openerKey is not None
    numFontsFunc, openerFunc, getSortInfo = fontOpeners[openerKey]
    return numFontsFunc, openerFunc, getSortInfo


def sniffFontType(fontPath: PathLike):
    if not isinstance(fontPath, PathLike):
        raise TypeError("fontPath must be a Path(-like) object")
    openerKey = fontPath.suffix.lower().lstrip(".")
    if openerKey not in fontOpeners:
        return None
    return openerKey


defaultSortSpec = ("familyName", "weight", "width", "italicAngle", "styleName", "suffix")


def sortedFontPathsAndNumbers(paths: list, sortSpec: tuple=()):
    expandedPaths = list(iterFontPathsAndNumbers(paths))

    def sorter(item):
        path, fontNum, getSortInfo = item
        sortInfo = getSortInfo(path, fontNum)
        return tuple(sortInfo.get(key, defaultSortInfo[key]) for key in sortSpec)

    expandedPaths.sort(key=sorter)
    return [(fontPath, fontNum) for fontPath, fontNum, getSortInfo in expandedPaths]


def iterFontPathsAndNumbers(paths: list):
    for path in paths:
        if sniffFontType(path) is None and path.is_dir():
            for child in sorted(path.iterdir()):
                yield from iterFontNumbers(child)
        else:
            yield from iterFontNumbers(path)


def iterFontNumbers(path):
    if sniffFontType(path) is None:
        return
    numFonts, opener, getSortInfo = getOpener(path)
    for i in range(numFonts(path)):
        yield path, i, getSortInfo


def openOTF(fontPath: PathLike, fontNumber: int, fontData=None):
    from .otfFont import OTFFont
    if fontData is not None:
        font = OTFFont(fontData, fontNumber)
    else:
        font = OTFFont.fromPath(fontPath, fontNumber)
        fontData = font.fontData
    return (font, fontData)


def openTTX(fontPath: PathLike, fontNumber: int, fontData=None):
    from .otfFont import TTXFont
    font = TTXFont(fontPath, 0)
    return (font, None)


def openUFO(fontPath: PathLike, fontNumber: int, fontData=None):
    from .ufoFont import UFOFont
    assert fontData is None  # dummy
    font = UFOFont(fontPath)
    return (font, None)


def openDS(fontPath: PathLike, fontNumber: int, fontData=None):
    from .dsFont import DSFont
    assert fontData is None  # dummy
    font = DSFont(fontPath)
    return (font, None)


def numFontsOne(fontPath: PathLike):
    return 1


def numFontsTTC(fontPath: PathLike):
    from fontTools.ttLib.sfnt import readTTCHeader
    with open(fontPath, "rb") as f:
        header = readTTCHeader(f)
    return header.numFonts


defaultSortInfo = dict(familyName="", styleName="", weight=400, width=5, italicAngle=0, suffix="")


def getSortInfoOTF(fontPath: PathLike, fontNum: int):
    from fontTools.ttLib import TTFont
    suffix = fontPath.suffix.lower().lstrip(".")
    ttf = TTFont(fontPath, fontNumber=fontNum, lazy=True)
    sortInfo = dict(suffix=suffix)
    name = ttf.get("name")
    os2 = ttf.get("OS/2")
    post = ttf.get("post")
    if name is not None:
        for key, nameIDs in [("familyName", [16, 1]), ("styleName", [17, 2])]:
            for nameID in nameIDs:
                nameRec = name.getName(nameID, 3, 1)
                if nameRec is not None:
                    sortInfo[key] = str(nameRec)
                    break
    if os2 is not None:
        sortInfo["weight"] = os2.usWeightClass
        sortInfo["width"] = os2.usWidthClass
    if post is not None:
        sortInfo["italicAngle"] = -post.italicAngle  # negative for intuitive sort order
    return sortInfo


def getSortInfoUFO(fontPath: PathLike, fontNum: int):
    from fontTools.ufoLib import UFOReader
    assert fontNum == 0
    suffix = fontPath.suffix.lower().lstrip(".")
    reader = UFOReader(fontPath, validate=False)
    info = SimpleNamespace()
    reader.readInfo(info)
    sortInfo = dict(suffix=suffix)
    ufoAttrs = [
        ("familyName", "familyName"),
        ("styleName", "styleName"),
        ("weight", "openTypeOS2WeightClass"),
        ("width", "openTypeOS2WidthClass"),
        ("italicAngle", "italicAngle"),
    ]
    for key, attr in ufoAttrs:
        val = getattr(info, attr, None)
        if val is not None:
            if key == "italicAngle":
                val = -val  # negative for intuitive sort order
            sortInfo[key] = val
    return sortInfo


def getSortInfoDS(fontPath: PathLike, fontNum: int):
    assert fontNum == 0
    return {}  # TODO


def getSortInfoTTX(fontPath: PathLike, fontNum: int):
    assert fontNum == 0
    return {}  # not really possible in a fast way


fontOpeners = {
    "ttf": (numFontsOne, openOTF, getSortInfoOTF),
    "otf": (numFontsOne, openOTF, getSortInfoOTF),
    "woff": (numFontsOne, openOTF, getSortInfoOTF),
    "woff2": (numFontsOne, openOTF, getSortInfoOTF),
    "ufo": (numFontsOne, openUFO, getSortInfoUFO),
    "ufos": (numFontsOne, openUFO, getSortInfoUFO),
    "ttc": (numFontsTTC, openOTF, getSortInfoOTF),
    "otc": (numFontsTTC, openOTF, getSortInfoOTF),
    "designspace": (numFontsOne, openDS, getSortInfoDS),
    "ttx": (numFontsOne, openTTX, getSortInfoTTX),
}

fileTypes = sorted(fontOpeners)


def mergeScriptsAndLanguages(*dicts):
    if not dicts:
        return dict()
    merged = dict(dicts[0])
    for d in dicts[1:]:
        for k, v in d.items():
            if k in merged:
                merged[k] = merged[k] | v  # not |= as we _don't_ want to modify in-place!
            else:
                merged[k] = v
    return merged


def _defaultValueToSet(axis):
    return {k: v if k != "defaultValue" or isinstance(v, set) else {v} for k, v in axis.items()}


def mergeAxes(*axesList):
    merged = {}
    for axes in axesList:
        for tag, axis in axes.items():
            axis = _defaultValueToSet(axis)
            if tag in merged:
                mergedAxis = merged[tag]
                mergedAxis["defaultValue"] |= axis["defaultValue"]
                mergedAxis["minValue"] = min(mergedAxis["minValue"], axis["minValue"])
                mergedAxis["maxValue"] = max(mergedAxis["maxValue"], axis["maxValue"])
            else:
                merged[tag] = axis
    return merged
