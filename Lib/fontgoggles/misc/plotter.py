from fontTools.pens.recordingPen import RecordingPen
from os import environ

"""
An abstraction on top of CocoaPen / any Mac-specific operations
so that fontGoggles can function as a platform-agnostic library
"""

COCOA = bool(int(environ.get("FONTGOGGLES_COCOA", "1")))

try:
    from fontTools.pens.cocoaPen import CocoaPen
except ImportError:
    COCOA = False


from uharfbuzz import DrawFuncs

rp_draw_funcs = DrawFuncs()

def move_to(x,y,c):
    c.append(("moveTo", ((x,y),)))
def line_to(x,y,c):
    c.append(("lineTo", ((x,y),)))
def cubic_to(c1x,c1y,c2x,c2y,x,y,c):
    c.append(("curveTo", ((c1x,c1y),(c2x,c2y),(x,y))))
def quadratic_to(c1x,c1y,x,y,c):
    c.append(("qCurveTo", ((c1x,c1y),(x,y))))
def close_path(c):
    c.append(("closePath", ()))

rp_draw_funcs.set_move_to_func(move_to)
rp_draw_funcs.set_line_to_func(line_to)
rp_draw_funcs.set_cubic_to_func(cubic_to)
rp_draw_funcs.set_quadratic_to_func(quadratic_to)
rp_draw_funcs.set_close_path_func(close_path)

class Plotter():
    def __init__(self, glyphSet, path=None):
        if COCOA:
            self.pen = CocoaPen(glyphSet, path=path)
        else:
            self.pen = RecordingPen(glyphSet, path=path)
        
    def draw(self, pen):
        self.pen.draw(pen)
    
    def getOutline(self):
        if isinstance(self.pen, CocoaPen):
            return self.pen.path
        else:
            return self.pen


def pathFromArrays(font, points, tags, contours):
    if COCOA:
        from ..mac.makePathFromOutline import makePathFromArrays
        return makePathFromArrays(points, tags, contours)
    else:
        rp = RecordingPen()
        font.draw(rp)
        return rp


def pathFromGlyph(font, gid):
    if COCOA:
        from ..mac.makePathFromOutline import makePathFromGlyph
        return makePathFromGlyph(font, gid)
    else:
        container = []
        font.draw_glyph(gid, rp_draw_funcs, container)
        rp = RecordingPen()
        rp.value = container
        return rp


def convertRect(r):
    if COCOA:
        from ..mac.drawing import rectFromNSRect
        return rectFromNSRect(r)


def convertColor(c):
    if COCOA:
        from ..mac.drawing import nsColorFromRGBA
        return nsColorFromRGBA(c)