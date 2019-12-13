from os import PathLike


def getOpener(path:PathLike):
    openerKey = sniffFontType(path)
    assert openerKey is not None
    numFontsFunc, openerFunc = fontOpeners[openerKey]
    return numFontsFunc, openerFunc


def sniffFontType(path:PathLike):
    if not isinstance(path, PathLike):
        raise TypeError("path must be a Path(-like) object")
    assert path.is_file()
    openerKey = path.suffix.lower().lstrip(".")
    if openerKey not in fontOpeners:
        return None
    return openerKey


async def openOTF(fontPath:PathLike, fontNumber:int, fontData=None):
    from .baseFont import OTFFont
    if fontData is not None:
        font = OTFFont(fontData, fontNumber)
    else:
        font = OTFFont.fromPath(fontPath, fontNumber)
        fontData = font.fontData
    return (font, fontData)


def numFontsOTF(path:PathLike):
    return 1


def numFontsTTC(path:PathLike):
    from fontTools.ttLib.sfnt import readTTCHeader
    with open(path, "rb") as f:
        header = readTTCHeader(f)
    return header.numFonts


fontOpeners = {
    "ttf":   (numFontsOTF, openOTF),
    "otf":   (numFontsOTF, openOTF),
    "woff":  (numFontsOTF, openOTF),
    "woff2": (numFontsOTF, openOTF),
    "ttc":   (numFontsTTC, openOTF),
    "otc":   (numFontsTTC, openOTF),
}
