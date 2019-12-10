import pathlib
import pytest
from fontTools.pens.recordingPen import RecordingPen, RecordingPointPen
from fontTools.pens.cocoaPen import CocoaPen
from fontTools.ttLib import TTFont
from fontgoggles.misc.ftFont import FTFont
import Quartz


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


def _comparePaths(path1, path2):
    return Quartz.CGPathEqualToPath(path1.CGPath(), path2.CGPath())


def test_getOutlinePath():
    ftf, ttfGlyphSet = _getFonts("IBMPlexSans-Regular.ttf")

    for glyphName in ["a", "B", "O", "period", "bar", "aring"]:
        p = ftf.getOutlinePath(glyphName)
        pen = CocoaPen(ttfGlyphSet)
        ttfGlyphSet[glyphName].draw(pen)
        assert _comparePaths(p, pen.path)
