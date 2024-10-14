import pytest
from asyncio import run
from fontgoggles.font import getOpener
from fontgoggles.misc.textInfo import TextInfo
from testSupport import getFontPath
from fontTools.pens.recordingPen import RecordingPen

from fontgoggles.misc.plotter import Plotter


def test_cocoaAndNoCocoa():
    def getDrawings():
        fontPath = getFontPath("MutatorSans.ttf")
        _, opener, _ = getOpener(fontPath)
        font = opener(fontPath, 0)
        run(font.load(None)) # to test support for non-async
        
        textInfo = TextInfo("abc")
        glyphs = font.getGlyphRunFromTextInfo(textInfo)
        glyphNames = [g.name for g in glyphs]
        glyphDrawings = list(font.getGlyphDrawings(glyphNames, True))

        assert len(glyphs) == 3
        assert len(glyphDrawings) == 3

        return glyphDrawings

    glyphDrawings = getDrawings()
    for g in glyphDrawings:
        assert "NSBezierPath" in str(type(g.path))

    Plotter.UseCocoa = False
    glyphDrawings = getDrawings()
    for g in glyphDrawings:
        assert isinstance(g.path, RecordingPen)