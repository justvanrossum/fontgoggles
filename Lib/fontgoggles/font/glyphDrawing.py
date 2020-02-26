from fontTools.misc.arrayTools import unionRect
from ..mac.drawing import rectFromNSRect
from ..misc.properties import cachedProperty


class GlyphDrawing:

    def __init__(self, layers=None):
        self.layers = layers

    def appendPath(self, path, colorID=None):
        self.layers.append((path, colorID))

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
