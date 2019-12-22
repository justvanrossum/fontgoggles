import functools
import weakref
import AppKit
from vanilla import Group
from fontgoggles.misc.decorators import delegateProperty, hookedProperty
from fontgoggles.mac.drawing import rgbColor, grayColor, drawText


updatingProperty = functools.partial(hookedProperty, lambda obj: obj.setNeedsDisplay_(True))


class FGTagView(AppKit.NSView):

    tag = updatingProperty()
    state = updatingProperty()
    tracked = updatingProperty(default=False)

    def mouseDown_(self, event):
        point = self.convertPoint_fromView_(event.locationInWindow(), None)
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
            g = 0.6
            mainRGB = (g, g, g)
        elif self.state:
            mainRGB = (0, 0.7, 0.2)
        else:
            mainRGB = (0.9, 0.2, 0.4)

        newState = self.state
        if self.tracked:
            mainRGB = tuple(0.6 * ch for ch in mainRGB)
            newState = self.toggledState()

        mainColor = rgbColor(*mainRGB)
        mainColor.set()
        radius = min(h/2.75, 10)
        path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(self.bounds(), radius, radius)
        path.fill()

        textColor = grayColor(1)
        drawText(self.tag, (x + 12, y + 1), textColor, AppKit.NSFont.userFixedPitchFontOfSize_(14))


class TagView(Group):

    nsViewClass = FGTagView
    tag = delegateProperty("_nsObject")
    state = delegateProperty("_nsObject")

    def __init__(self, posSize, tag, state, callback=None):
        super().__init__(posSize)
        self.tag = tag
        self.state = state
        if callback is not None:
            self._callbackRef = weakref.WeakMethod(callback)
        else:
            self._callbackRef = lambda: None

    def _callCallback(self):
        callback = self._callbackRef()
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
