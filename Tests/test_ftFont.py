import pathlib
import pytest
from fontTools.pens.recordingPen import RecordingPen, RecordingPointPen
from fontTools.ttLib import TTFont
from fontgoggles.misc.ftFont import FTFont


testRoot = pathlib.Path(__file__).resolve().parent


def getFontPath(fileName):
    return testRoot / "data" / fileName


def test_getOutline():
    p = getFontPath("IBMPlexSans-Regular.ttf")
    ftf = FTFont.fromPath(p)
    ttf = TTFont(p, lazy=True)
    ttfGlyphSet = ttf.getGlyphSet()

    for glyphName in ["a", "B", "O", "period"]:
        refPen = RecordingPen()
        ttfGlyphSet[glyphName].draw(refPen)
        pen = RecordingPen()
        ftf.drawGlyphToPen(glyphName, pen)
        assert pen.value == refPen.value

        refPen = RecordingPointPen()
        ttfGlyphSet[glyphName].drawPoints(refPen)
        pen = RecordingPointPen()
        ftf.drawGlyphToPointPen(glyphName, pen)
        assert pen.value == refPen.value
