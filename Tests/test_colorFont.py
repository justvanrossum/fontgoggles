import pytest
from AppKit import NSGraphicsContext, NSColor
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
    bounds = glyphDrawing.bounds
    assert (100, 0, 900, 1000) == bounds
    x, y, w, h = bounds
    w -= x
    h -= y
    surface = CoreGraphicsPixelSurface(x, y, w, h)
    context = NSGraphicsContext.graphicsContextWithCGContext_flipped_(surface.context, False)
    savedContext = NSGraphicsContext.currentContext()
    palette = [
        NSColor.colorWithCalibratedRed_green_blue_alpha_(*c)
        for c in glyphDrawing.colorFont.palettes[0]
    ]
    try:
        NSGraphicsContext.setCurrentContext_(context)
        glyphDrawing.draw(palette, NSColor.blackColor())
    finally:
        NSGraphicsContext.setCurrentContext_(savedContext)
