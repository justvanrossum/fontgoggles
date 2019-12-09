import pathlib
import pytest
from fontTools.pens.recordingPen import RecordingPen, RecordingPointPen
from fontTools.ttLib import TTFont
from fontgoggles.misc.ftFont import FTFont


testRoot = pathlib.Path(__file__).resolve().parent


def getFontPath(fileName):
    return testRoot / "data" / fileName


def _getFonts(fileName):
    p = getFontPath(fileName)
    ttf = TTFont(p, lazy=True)
    return FTFont.fromPath(p), ttf.getGlyphSet()


def test_getDrawToPen():
    ftf, ttfGlyphSet = _getFonts("IBMPlexSans-Regular.ttf")
    for glyphName in ["a", "B", "O", "period"]:
        refPen = RecordingPen()
        ttfGlyphSet[glyphName].draw(refPen)
        pen = RecordingPen()
        ftf.drawGlyphToPen(glyphName, pen)
        assert pen.value == refPen.value


def test_getDrawToPointPen():
    ftf, ttfGlyphSet = _getFonts("IBMPlexSans-Regular.ttf")
    for glyphName in ["a", "B", "O", "period"]:
        refPen = RecordingPointPen()
        ttfGlyphSet[glyphName].drawPoints(refPen)
        pen = RecordingPointPen()
        ftf.drawGlyphToPointPen(glyphName, pen)
        assert pen.value == refPen.value
