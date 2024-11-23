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


class Platform():
    UseCocoa = CAN_COCOA

    @staticmethod
    def pathFromArrays(font, points, tags, contours):
        if Platform.UseCocoa:
            from ..mac.makePathFromOutline import makePathFromArrays
            return makePathFromArrays(points, tags, contours)
        else:
            rp = RecordingPen()
            font.draw(rp)
            return rp

    @staticmethod
    def pathFromGlyph(font, gid):
        if Platform.UseCocoa:
            from ..mac.makePathFromOutline import makePathFromGlyph
            return makePathFromGlyph(font, gid)
        else:
            rp = RecordingPen()
            font.draw_glyph_with_pen(gid, rp)
            return rp

    @staticmethod
    def convertRect(r):
        if Platform.UseCocoa:
            from ..mac.drawing import rectFromNSRect
            return rectFromNSRect(r)

    @staticmethod
    def convertColor(c):
        if Platform.UseCocoa:
            from ..mac.drawing import nsColorFromRGBA
            return nsColorFromRGBA(c)
        
    @staticmethod
    def drawCOLRv1Glyph(colorFont, glyphName, colorPalette, defaultColor):
        if Platform.UseCocoa:
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


class PlatformPenWrapper():
    def __init__(self, glyphSet, path=None):
        if Platform.UseCocoa:
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