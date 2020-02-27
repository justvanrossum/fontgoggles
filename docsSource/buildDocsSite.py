#!/usr/bin/env python

import os
import pathlib
import time
from fontTools.ufoLib import plistlib
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

indexMD = docsSourceDir / "index.md"
markdownSource = indexMD.read_text(encoding="utf-8")

mdConverter = markdown.Markdown()
htmlIndex = docsDir / "index.html"
htmlIndex.write_text(htmlTemplate % mdConverter.convert(markdownSource), encoding="utf-8")
