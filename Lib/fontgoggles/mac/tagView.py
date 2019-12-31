import AppKit
from vanilla import Group
from fontgoggles.misc.properties import delegateProperty, hookedProperty, weakrefCallbackProperty
from fontgoggles.mac.drawing import rgbColor, grayColor, drawText


class FGTagView(AppKit.NSView):

    def _scheduleRedraw(self):
        self.setNeedsDisplay_(True)

    tag = hookedProperty(_scheduleRedraw)
    state = hookedProperty(_scheduleRedraw)
    tracked = hookedProperty(_scheduleRedraw, default=False)

    def mouseDown_(self, event):
        self.tracked = True

    def mouseDragged_(self, event):
        point = self.convertPoint_fromView_(event.locationInWindow(), None)
        self.tracked = AppKit.NSPointInRect(point, self.bounds())

    def mouseUp_(self, event):
        point = self.convertPoint_fromView_(event.locationInWindow(), None)
        self.tracked = False
        if AppKit.NSPointInRect(point, self.bounds()):
            self.toggleState()
            self.vanillaWrapper()._callCallback()

    def toggledState(self):
        if self.state is None:
            newState = True
        elif self.state:
            newState = False
        else:
            newState = None
        return newState

    def toggleState(self):
        self.state = self.toggledState()

    def drawRect_(self, rect):
        (x, y), (w, h) = self.bounds()
        if self.state is None:
            mainColor = AppKit.NSColor.systemGrayColor()
        elif self.state:
            mainColor = AppKit.NSColor.systemGreenColor()
            mainColor = mainColor.blendedColorWithFraction_ofColor_(0.25, AppKit.NSColor.systemGrayColor())
        else:
            mainColor = AppKit.NSColor.systemRedColor()

        if self.tracked:
            mainColor = mainColor.blendedColorWithFraction_ofColor_(0.5, AppKit.NSColor.textColor())

        mainColor.set()
        radius = min(h / 2.75, 10)
        path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(self.bounds(), radius, radius)
        path.fill()

        textColor = AppKit.NSColor.textBackgroundColor()
        drawText(self.tag, (x + 12, y + 1), textColor, AppKit.NSFont.userFixedPitchFontOfSize_(14))


class TagView(Group):

    nsViewClass = FGTagView
    tag = delegateProperty("_nsObject")
    state = delegateProperty("_nsObject")
    _callback = weakrefCallbackProperty()

    def __init__(self, posSize, tag, state, callback=None):
        super().__init__(posSize)
        self.tag = tag
        self.state = state
        self._callback = callback

    def _callCallback(self):
        callback = self._callback
        if callback is not None:
            callback(self)


if __name__ == "__main__":
    from vanilla import *

    class Test:

        def __init__(self):
            self.w = Window((300, 500), minSize=(200, 100))
            y = 10
            self.w.g = Group((0, 0, 0, 0))
            for i, tag in enumerate(["liga", "calt", "dlig", "smcp", "kern", "locl"]):
                setattr(self.w.g, f"tag{i}", TagView((10, y, 60, 20), tag, None, self.callback))
                y += 26
            self.w.open()

        def callback(self, sender):
            print("---", sender.tag, sender.state)

    t = Test()
