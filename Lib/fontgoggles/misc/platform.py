from types import SimpleNamespace
from fontTools.pens.recordingPen import RecordingPen

"""
An abstraction on top of CocoaPen / any Mac-specific operations
so that fontGoggles can function as a platform-agnostic library
"""


CAN_COCOA = True

try:
    from fontTools.pens.cocoaPen import CocoaPen
except ImportError:
    CAN_COCOA = False

USE_COCOA = CAN_COCOA


class PlatformCocoa:
    @staticmethod
    def pathFromArrays(font, points, tags, contours):
        from ..mac.makePathFromOutline import makePathFromArrays

        return makePathFromArrays(points, tags, contours)

    @staticmethod
    def pathFromGlyph(font, gid):
        from ..mac.makePathFromOutline import makePathFromGlyph

        return makePathFromGlyph(font, gid)

    @staticmethod
    def convertRect(r):
        from ..mac.drawing import rectFromNSRect

        return rectFromNSRect(r)

    @staticmethod
    def convertColor(c):
        from ..mac.drawing import nsColorFromRGBA

        return nsColorFromRGBA(c)

    @staticmethod
    def drawCOLRv1Glyph(colorFont, glyphName, colorPalette, defaultColor):
        from AppKit import NSGraphicsContext
        from blackrenderer.backends.coregraphics import CoreGraphicsCanvas

        cgContext = NSGraphicsContext.currentContext().CGContext()
        colorFont.drawGlyph(
            glyphName,
            CoreGraphicsCanvas(cgContext),
            palette=colorPalette,
            textColor=defaultColor,
        )
    
    Pen = CocoaPen


class PlatformGeneric:
    @staticmethod
    def pathFromArrays(font, points, tags, contours):
        rp = RecordingPen()
        font.draw(rp)
        return rp

    @staticmethod
    def pathFromGlyph(font, gid):
        rp = RecordingPen()
        font.draw_glyph_with_pen(gid, rp)
        return rp

    @staticmethod
    def convertRect(r):
        raise NotImplementedError()

    @staticmethod
    def convertColor(c):
        raise NotImplementedError()

    @staticmethod
    def drawCOLRv1Glyph(colorFont, glyphName, colorPalette, defaultColor):
        raise NotImplementedError()
    
    class Pen(RecordingPen):
        def __init__(self, glyphSet): # to match CocoaPen constructor
            super().__init__()
        
        @property
        def path(self):
            return self


platform = SimpleNamespace()

_platform = PlatformCocoa if CAN_COCOA else PlatformGeneric
platform.__dict__.update(**_platform.__dict__)


def setUseCocoa(onOff):
    global platform
    if onOff:
        assert CAN_COCOA
    _platform = PlatformCocoa if onOff else PlatformGeneric
    platform.__dict__.update(**_platform.__dict__)


def getUseCocoa():
    return platform is PlatformCocoa
