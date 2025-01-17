import sys
import pytest
from fontTools.ttLib import TTFont
from fontgoggles.font.otfFont import OTFFont
from fontgoggles.misc.platform import platform
from testSupport import getFontPath


def _getFonts(fileName):
    p = getFontPath(fileName)
    ttf = TTFont(p, lazy=True)
    return OTFFont(p, 0), ttf.getGlyphSet()


@pytest.mark.asyncio
async def test_getOutlinePath():
    font, ttfGlyphSet = _getFonts("IBMPlexSans-Regular.ttf")
    await font.load(sys.stderr.write)

    for glyphName in ["a", "B", "O", "period", "bar", "aring"]:
        p = font._getGlyphOutline(glyphName)
        pen = platform.Pen(ttfGlyphSet)
        ttfGlyphSet[glyphName].draw(pen)
        # The paths are not identical, due to different rounding
        # of the implied points, and different closepath behavior,
        # so comparing is hard, so we'll settle for a bounding box.
        assert p.controlPointBounds() == pen.path.controlPointBounds()


@pytest.mark.asyncio
async def test_getOutlinePath_singleOffCurve():
    font, ttfGlyphSet = _getFonts("QuadTest-Regular.ttf")
    await font.load(sys.stderr.write)

    for glyphName in ["b"]:
        p = font._getGlyphOutline(glyphName)
        (x, y), (w, h) = p.controlPointBounds()
        assert (x, y, w, h) == (0, 50, 0, 0)
        assert p.elementCount() == 4
