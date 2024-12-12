import pytest, sys
from asyncio import run
from fontgoggles.font import getOpener
from fontgoggles.misc.textInfo import TextInfo
from testSupport import getFontPath
from fontTools.pens.recordingPen import RecordingPen

import fontgoggles.misc.platform as platform

font_paths = [
    "MutatorSans.ttf",
    "MutatorSansBoldWide.ufo",
    "MutatorSans.designspace",
]


def test_cocoaAndNoCocoa():
    def getDrawings(path):
        fontPath = getFontPath(path)
        _, opener, _ = getOpener(fontPath)
        font = opener(fontPath, 0)
        run(font.load(sys.stderr.write))  # to test support for non-async

        textInfo = TextInfo("abc")
        glyphs = font.getGlyphRunFromTextInfo(textInfo)
        glyphNames = [g.name for g in glyphs]
        glyphDrawings = list(font.getGlyphDrawings(glyphNames, True))

        assert len(glyphs) == 3
        assert len(glyphDrawings) == 3

        return glyphDrawings

    for font_path in font_paths:
        glyphDrawings = getDrawings(font_path)
        for g in glyphDrawings:
            assert "NSBezierPath" in str(type(g.path))

    platform.USE_COCOA = False

    for font_path in font_paths:
        glyphDrawings = getDrawings(font_path)
        for g in glyphDrawings:
            assert isinstance(g.path, RecordingPen)
