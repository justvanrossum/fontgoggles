import AppKit
import vanilla
from ..misc.decorators import hookedProperty


class AligningScrollView(vanilla.ScrollView):

    """ScrollView aligning its document view according to the `hAlign` and `vAlign`
    parameters.

    `hAlign` can be "left" (default), "center" or "right"
    `vAlign` can be "top" (default), "center" or "bottom"
    """

    def __init__(self, posSize, documentView, hAlign="left", vAlign="top",
                 drawBackground=True, minMagnification=None, maxMagnification=None,
                 borderType=AppKit.NSBezelBorder, clipview=None):
        self._docRef = [documentView]
        if hasattr(documentView, "_nsObject"):
            x, y, w, h = documentView._posSize
            assert x == 0 and y == 0, "posSize x and y must be 0 in document view"
            assert w >= 0 and h >= 0, "posSize w and h must be positive in document view"
            documentView = documentView._nsObject
            documentView.setFrame_(((0, 0), (w, h)))
        if clipview is None:
            clipView = _AligningScrollView_ClipView(hAlign, vAlign)
        super().__init__(posSize, documentView, clipView=clipView)
        clipView.setDrawsBackground_(drawBackground)  # Must be called _after_ super()
        scrollView = self._nsObject
        scrollView.setBorderType_(borderType)
        if maxMagnification is not None:
            scrollView.setAllowsMagnification_(True)
            scrollView.setMaxMagnification_(maxMagnification)
        if minMagnification is not None:
            scrollView.setAllowsMagnification_(True)
            scrollView.setMinMagnification_(minMagnification)

    @property
    def hAlign(self):
        return self._nsObject.contentView().hAlign

    @hAlign.setter
    def hAlign(self, value):
        self._nsObject.contentView().hAlign = value

    @property
    def vAlign(self):
        return self._nsObject.contentView().vAlign

    @vAlign.setter
    def vAlign(self, value):
        self._nsObject.contentView().vAlign = value


class _AligningScrollView_ClipView(AppKit.NSClipView):

    def __new__(cls, hAlign, vAlign):
        return cls.alloc().init()

    def __init__(self, hAlign, vAlign):
        self.hAlign = hAlign
        self.vAlign = vAlign
        self._prevClipBounds = self.bounds()
        self._prevDocBounds = None

    def mouseDown_(self, event):
        # A click occured in the clipview, but outside the document view. Happens when it is
        # smaller than the clipview. Make the document view first responder.
        self.window().makeFirstResponder_(self.documentView())

    @hookedProperty
    def hAlign(self):
        self.setBounds_(self.constrainBoundsRect_(self.bounds()))

    @hookedProperty
    def vAlign(self):
        self.setBounds_(self.constrainBoundsRect_(self.bounds()))

    def viewFrameChanged_(self, notification):
        docBounds = self.documentView().bounds()
        if self._prevDocBounds is None:
            self._prevDocBounds = docBounds
            return

        widthDiff = docBounds.size.width - self._prevDocBounds.size.width

        # Given what we know about our alignment, try to keep the scroll
        # position "the same". So if we are right aligned and we grow,
        # grow to the left. If we are centered, grow left and right.
        clipBounds = self.bounds()
        if clipBounds.size.width < docBounds.size.width:
            if self.hAlign == "right":
                clipBounds.origin.x += widthDiff
            elif self.hAlign == "center":
                clipBounds.origin.x += widthDiff / 2
            self.setBounds_(clipBounds)
        # else: handled by self.constrainBoundsRect_()

        # TODO: handle vertical alignments

        self._prevDocBounds = docBounds
        super().viewFrameChanged_(notification)

    def constrainBoundsRect_(self, proposedClipViewBoundsRect):
        # Partially taken from https://stackoverflow.com/questions/22072105/
        rect = super().constrainBoundsRect_(proposedClipViewBoundsRect)
        docView = self.documentView()
        if docView is None:
            return rect
        docBounds = docView.bounds()

        if self._prevClipBounds is not None:
            clipBounds = self.bounds()
            dx = clipBounds.origin.x - self._prevClipBounds.origin.x
            dy = clipBounds.origin.y - self._prevClipBounds.origin.y
            dw = clipBounds.size.width - self._prevClipBounds.size.width
            dh = clipBounds.size.height - self._prevClipBounds.size.height
        else:
            dx = dy = dw = dh = 0

        if rect.size.width > docBounds.size.width:
            if self.hAlign == "center":
                rect.origin.x = (docBounds.size.width - rect.size.width) / 2.0
            elif self.hAlign == "left":
                rect.origin.x = 0
            elif self.hAlign == "right":
                rect.origin.x = (docBounds.size.width - rect.size.width)
        else:
            if self.hAlign == "center":
                rect.origin.x = self._prevClipBounds.origin.x - dw / 2 + dx
            elif self.hAlign == "right":
                rect.origin.x = self._prevClipBounds.origin.x - dw + dx

        if rect.size.height > docBounds.size.height:
            if docView.isFlipped():
                if self.vAlign == "center":
                    rect.origin.y = (docBounds.size.height - rect.size.height) / 2.0
                elif self.vAlign == "top":
                    rect.origin.y = (docBounds.size.height - rect.size.height)
                elif self.vAlign == "bottom":
                    rect.origin.y = 0
            else:
                if self.vAlign == "center":
                    rect.origin.y = -(docBounds.size.height - rect.size.height) / 2.0
                elif self.vAlign == "top":
                    rect.origin.y = 0
                elif self.vAlign == "bottom":
                    rect.origin.y = -(docBounds.size.height - rect.size.height)
        else:
            # TODO implement alignment for vertical
            pass

        self._prevClipBounds = rect
        return rect
