from fontTools.pens.recordingPen import RecordingPen

"""
An abstraction on top of CocoaPen / any Mac-specific operations
so that fontGoggles can function as a platform-agnostic library
"""


CAN_COCOA = True

try:
    from fontTools.pens.cocoaPen import CocoaPen
    # TODO some other feature detection?
except ImportError:
    CAN_COCOA = False


recordingPenDrawFuncs = None

def build_draw_funcs():
    from uharfbuzz import DrawFuncs

    global recordingPenDrawFuncs
    recordingPenDrawFuncs = DrawFuncs()

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

    recordingPenDrawFuncs.set_move_to_func(move_to)
    recordingPenDrawFuncs.set_line_to_func(line_to)
    recordingPenDrawFuncs.set_cubic_to_func(cubic_to)
    recordingPenDrawFuncs.set_quadratic_to_func(quadratic_to)
    recordingPenDrawFuncs.set_close_path_func(close_path)


class Plotter():
    UseCocoa = CAN_COCOA

    def __init__(self, glyphSet, path=None):
        if Plotter.UseCocoa:
            self.pen = CocoaPen(glyphSet, path=path)
        else:
            self.pen = RecordingPen()
        
    def draw(self, pen):
        self.pen.draw(pen)
    
    def getOutline(self):
        if isinstance(self.pen, CocoaPen):
            return self.pen.path
        else:
            return self.pen

    @staticmethod
    def pathFromArrays(font, points, tags, contours):
        if Plotter.UseCocoa:
            from ..mac.makePathFromOutline import makePathFromArrays
            return makePathFromArrays(points, tags, contours)
        else:
            rp = RecordingPen()
            font.draw(rp)
            return rp

    @staticmethod
    def pathFromGlyph(font, gid):
        if Plotter.UseCocoa:
            from ..mac.makePathFromOutline import makePathFromGlyph
            return makePathFromGlyph(font, gid)
        else:
            container = []
            if recordingPenDrawFuncs is None:
                build_draw_funcs()
            font.draw_glyph(gid, recordingPenDrawFuncs, container)
            rp = RecordingPen()
            rp.value = container
            return rp

    @staticmethod
    def convertRect(r):
        if Plotter.UseCocoa:
            from ..mac.drawing import rectFromNSRect
            return rectFromNSRect(r)

    @staticmethod
    def convertColor(c):
        if Plotter.UseCocoa:
            from ..mac.drawing import nsColorFromRGBA
            return nsColorFromRGBA(c)
        
    @staticmethod
    def drawCOLRv1Glyph(colorFont, glyphName, colorPalette, defaultColor):
        if Plotter.UseCocoa:
            from AppKit import NSGraphicsContext
            from blackrenderer.backends.coregraphics import CoreGraphicsCanvas

            cgContext = NSGraphicsContext.currentContext().CGContext()
            colorFont.drawGlyph(
                glyphName,
                CoreGraphicsCanvas(cgContext),
                palette=colorPalette,
                textColor=defaultColor,
            )
        else:
            raise NotImplementedError()