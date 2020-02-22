#!/usr/bin/env python

import os
import pathlib
import time
from fontTools.ufoLib import plistlib
import markdown


rootDir = pathlib.Path(__file__).resolve().parent.parent
docsDir = rootDir / "docs"


htmlTemplate = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>FontGoggles — Rich Font Previewing and Comparing</title>
<link rel="stylesheet" href="markdown.css">
<style>
  html {
    margin-left: auto;
    margin-right: auto;
  }
  .headerlink {
    opacity: 0.0;
  }
  body h1:hover a.headerlink,
  body h2:hover a.headerlink,
  body h3:hover a.headerlink,
  body h4:hover a.headerlink {
    opacity: 1.0;
  }
</style>
</head>
<body>
%s
</body>
</html>
"""

indexMD = docsDir / "index.md"
markdownSource = indexMD.read_text(encoding="utf-8")

mdConverter = markdown.Markdown()
htmlIndex = docsDir / "index.html"
htmlIndex.write_text(htmlTemplate % mdConverter.convert(markdownSource), encoding="utf-8")
