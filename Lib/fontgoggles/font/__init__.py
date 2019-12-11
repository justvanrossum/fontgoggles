import os


async def openOTF(fontPath):
    from .baseFont import OTFFont
    yield await OTFFont.fromPath(fontPath)



async def openFonts(path):
    fontType = sniffFontType(path)
    opener = fontOpeners.get(fontType)
    if opener is not None:
        async for x in opener(path):
            yield x
        # yield opener(path)


fontOpeners = {
    "ttf": openOTF,
    "otf": openOTF,
    "woff": openOTF,
    "woff2": openOTF,
}


def sniffFontType(path):
    assert path.is_file()
    fontType = path.suffix.lower().lstrip(".")
    if fontType not in fontOpeners:
        return None
    return fontType
