#!/usr/bin/env python

import os
import pathlib
import shutil
import time
from fontTools.ufoLib import plistlib
from fontTools.subset import Subsetter
from fontTools.ttLib import TTFont
from PIL import Image
import markdown

docsSourceDir = pathlib.Path(__file__).resolve().parent
docsDir = docsSourceDir.parent / "docs"


htmlTemplate = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FontGoggles — Interactive Previewing and Comparing</title>
<link rel="stylesheet" href="markdown.css">
</style>
</head>
<body>
%s
</body>
</html>
"""


print("Generating html...")

indexMD = docsSourceDir / "index.md"
markdownSource = indexMD.read_text(encoding="utf-8")

mdConverter = markdown.Markdown()
htmlIndex = docsDir / "index.html"
htmlIndex.write_text(htmlTemplate % mdConverter.convert(markdownSource), encoding="utf-8")

docsImages = docsDir / "images"
docsSourceImages = docsSourceDir / "images"

docsFonts = docsDir / "fonts"
docsSourceFonts = docsSourceDir / "fonts"


print("Optizing images...")
for src in sorted(docsSourceImages.glob("*.png")):
    dst = docsImages / src.name
    im = Image.open(src)
    dpi = im.info.get("dpi", (72, 72))
    if dpi == (72, 72):
        shutil.copy(src, dst)
    else:
        w, h = im.size
        newW = round(w * (72 / dpi[0]))
        newH = round(h * (72 / dpi[0]))
        im = im.resize((newW, newH), Image.BICUBIC)
        # We round-trip through a buffer to workaround PIL not
        # resetting the dpi value.
        data = im.tobytes()
        im = Image.frombytes(im.mode, im.size, data)
        if dst.exists():
            dstIm = Image.open(dst)
            if data == dstIm.tobytes():
                # Don't save when the image data is the same, some
                # meta data may still have changed, making us do
                # unwanted commits.
                print("-- same image, skipping", dst)
                continue
        im.save(dst)


print("Subsetting fonts...")
for src in sorted(docsSourceFonts.glob("*.woff2")):
    dst = docsFonts / src.name
    font = TTFont(src)
    subsetter = Subsetter()
    unicodes = set(ord(c) for c in markdownSource)
    subsetter.populate(unicodes=unicodes)
    subsetter.subset(font)

    if dst.exists():
        existing = TTFont(dst, lazy=True)
        if sorted(font.getBestCmap()) == sorted(existing.getBestCmap()):
            print("-- same cmap, skipping", dst)
            continue
    font.flavor = "woff2"
    font.save(dst)
