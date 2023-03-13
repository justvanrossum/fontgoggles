import pytest
from AppKit import NSGraphicsContext
from blackrenderer.backends.coregraphics import CoreGraphicsPixelSurface
from fontgoggles.font import getOpener
from fontgoggles.misc.textInfo import TextInfo
from testSupport import getFontPath


@pytest.mark.asyncio
async def test_colrV1Font():
    fontPath = getFontPath("more_samples-glyf_colr_1.ttf")
    numFonts, opener, getSortInfo = getOpener(fontPath)
    font = opener(fontPath, 0)
    await font.load(None)
    textInfo = TextInfo("c")
    glyphs = font.getGlyphRunFromTextInfo(textInfo)
    glyphNames = [g.name for g in glyphs]
    glyphDrawing, *_ = font.getGlyphDrawings(glyphNames, True)
    boundingBox = glyphDrawing.bounds
    assert (100, 0, 900, 1000) == boundingBox
    surface = CoreGraphicsPixelSurface()
    with surface.canvas(boundingBox) as canvas:
        context = NSGraphicsContext.graphicsContextWithCGContext_flipped_(surface.context, False)
        savedContext = NSGraphicsContext.currentContext()
        try:
            NSGraphicsContext.setCurrentContext_(context)
            glyphDrawing.draw(glyphs.colorPalette, (0, 0, 0, 1))
        finally:
            NSGraphicsContext.setCurrentContext_(savedContext)
