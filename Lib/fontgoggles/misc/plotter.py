from fontTools.pens.recordingPen import RecordingPen

"""
An abstraction on top of CocoaPen / any Mac-specific operations
so that fontGoggles can function as a platform-agnostic library
"""

COCOA = True

try:
    from fontTools.pens.cocoaPen import CocoaPen
except ImportError:
    COCOA = False

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