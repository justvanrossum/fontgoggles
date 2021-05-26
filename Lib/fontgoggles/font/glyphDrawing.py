from AppKit import NSGraphicsContext
from fontTools.misc.arrayTools import unionRect
from ..mac.drawing import rectFromNSRect
from ..misc.properties import cachedProperty


class EmptyDrawing:

    bounds = None

    def draw(self, colorPalette, defaultColor):
        pass

    def pointInside(self, pt):
        return False


class GlyphDrawing:

    def __init__(self, path):
        self.path = path

    @cachedProperty
    def bounds(self):
        bounds = None
        if self.path.elementCount():
            bounds = rectFromNSRect(self.path.controlPointBounds())
        return bounds

    def draw(self, colorPalette, defaultColor):
        defaultColor.set()
        self.path.fill()

    def pointInside(self, pt):
        return self.path.containsPoint_(pt)


class GlyphLayersDrawing:

    def __init__(self, layers=None):
        self.layers = layers

    @cachedProperty
    def bounds(self):
        bounds = None
        for path, colorID in self.layers:
            if not path.elementCount():
                continue
            pathBounds = rectFromNSRect(path.controlPointBounds())
            if bounds is None:
                bounds = pathBounds
            else:
                bounds = unionRect(bounds, pathBounds)
        return bounds

    def draw(self, colorPalette, defaultColor):
        for path, colorID in self.layers:
            color = colorPalette.get(colorID, defaultColor)
            color.set()
            path.fill()

    def pointInside(self, pt):
        return any(path.containsPoint_(pt) for path, colorID in self.layers)


class GlyphCOLRv1Drawing:
    def __init__(self, glyphName, colorFont):
        self.glyphName = glyphName
        self.colorFont = colorFont

    @cachedProperty
    def bounds(self):
        return self.colorFont.getGlyphBounds(self.glyphName)

    def draw(self, colorPalette, defaultColor):
        from blackrenderer.backends.coregraphics import CoreGraphicsCanvas

        palette = [
            colorPalette[index].getRed_green_blue_alpha_(None, None, None, None)
            for index in range(len(colorPalette))
        ]

        cgContext = NSGraphicsContext.currentContext().CGContext()
        with self.colorFont.pushPalette(palette):
            self.colorFont.drawGlyph(self.glyphName, CoreGraphicsCanvas(cgContext))

    def pointInside(self, pt):
        return False  # TODO: implement
