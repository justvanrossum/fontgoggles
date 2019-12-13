import contextlib
import AppKit


__all__ = ["scale", "translate", "savedState", "nsRectFromRect", "rectFromNSRect"]


def scale(scaleX, scaleY=None):
    t = AppKit.NSAffineTransform.alloc().init()
    if scaleY is None:
        t.scaleBy_(scaleX)
    else:
        t.scaleXBy_yBy_(scaleX, scaleY)
    t.concat()


def translate(dx, dy):
    t = AppKit.NSAffineTransform.alloc().init()
    t.translateXBy_yBy_(dx, dy)
    t.concat()


@contextlib.contextmanager
def savedState():
    AppKit.NSGraphicsContext.saveGraphicsState()
    yield
    AppKit.NSGraphicsContext.restoreGraphicsState()


def nsRectFromRect(rect):
    xMin, yMin, xMax, yMax = rect
    return (xMin, yMin), (xMax - xMin, yMax - yMin)


def rectFromNSRect(nsRect):
    # To .misc.rectangle?
    (x, y), (w, h) = nsRect
    return x, y, x + w, y + h
