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
