import AppKit
import vanilla


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
        self._hAlign = hAlign
        self.vAlign = vAlign
        self._prevBounds = self.bounds()

    def mouseDown_(self, event):
        # A click occured in the clipview, but outside the document view. Happens when it is
        # smaller than the clipview. Make the document view first responder.
        self.window().makeFirstResponder_(self.documentView())

    @property
    def hAlign(self):
        return self._hAlign

    @hAlign.setter
    def hAlign(self, value):
        self._hAlign = value
        self.setBounds_(self.constrainBoundsRect_(self.bounds()))

    def constrainBoundsRect_(self, proposedClipViewBoundsRect):
        # Partially taken from https://stackoverflow.com/questions/22072105/
        rect = super().constrainBoundsRect_(proposedClipViewBoundsRect)
        view = self.documentView()
        viewFrame = view.bounds()

        if self._prevBounds is not None:
            dx = self.bounds().origin.x - self._prevBounds.origin.x
            dy = self.bounds().origin.y - self._prevBounds.origin.y
            dw = self.bounds().size.width - self._prevBounds.size.width
            dh = self.bounds().size.height - self._prevBounds.size.height
        else:
            dx = dy = dw = dh = 0

        # TODO: this does not work well together with magnification, at least not
        # When the document view is a vanilla group.

        if view is not None:
            if rect.size.width > viewFrame.size.width:
                if self.hAlign == "center":
                    rect.origin.x = (viewFrame.size.width - rect.size.width) / 2.0
                elif self.hAlign == "left":
                    rect.origin.x = 0
                elif self.hAlign == "right":
                    rect.origin.x = (viewFrame.size.width - rect.size.width)
            else:
                if self.hAlign == "center":
                    rect.origin.x = self._prevBounds.origin.x - dw / 2 + dx
                elif self.hAlign == "right":
                    rect.origin.x = self._prevBounds.origin.x - dw + dx

            if rect.size.height > viewFrame.size.height:
                if view.isFlipped():
                    if self.vAlign == "center":
                        rect.origin.y = (viewFrame.size.height - rect.size.height) / 2.0
                    elif self.vAlign == "top":
                        rect.origin.y = (viewFrame.size.height - rect.size.height)
                    elif self.vAlign == "bottom":
                        rect.origin.y = 0
                else:
                    if self.vAlign == "center":
                        rect.origin.y = -(viewFrame.size.height - rect.size.height) / 2.0
                    elif self.vAlign == "top":
                        rect.origin.y = 0
                    elif self.vAlign == "bottom":
                        rect.origin.y = -(viewFrame.size.height - rect.size.height)
            else:
                # TODO implement alignment for vertical
                pass

        self._prevBounds = rect
        return rect
