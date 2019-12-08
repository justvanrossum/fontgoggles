import pathlib
import pytest
from fontTools.pens.recordingPen import RecordingPen
from fontgoggles.misc.ftFont import FTFont


testRoot = pathlib.Path(__file__).resolve().parent


def getFontPath(fileName):
    return testRoot / "data" / fileName


def test_getOutline():
    f = FTFont.fromPath(getFontPath("IBMPlexSans-Regular.otf"))
    pen = RecordingPen()
    f.drawGlyphToPen("bar", pen)
    expected = [
        ('moveTo', ((191, -138),)),
        ('lineTo', ((191, 760),)),
        ('lineTo', ((123, 760),)),
        ('lineTo', ((123, -138),)),
        ('closePath', ()),
    ]
    assert pen.value == expected
