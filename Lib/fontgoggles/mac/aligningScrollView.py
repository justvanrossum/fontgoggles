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
            assert w > 0 and h > 0, "posSize w and h must be positive in document view"
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


class _AligningScrollView_ClipView(AppKit.NSClipView):

    def __new__(cls, hAlign, vAlign):
        return cls.alloc().init()

    def __init__(self, hAlign, vAlign):
        self.hAlign = hAlign
        self.vAlign = vAlign


    def mouseDown_(self, event):
        # A click occured in the clipview, but outside the document view. Happens when it is
        # smaller than the clipview. Make the document view first responder.
        self.window().makeFirstResponder_(self.documentView())

    def constrainBoundsRect_(self, proposedClipViewBoundsRect):
        # taken from https://stackoverflow.com/questions/22072105/how-do-you-get-nsscrollview-to-center-the-document-view-in-10-9-and-later
        rect = super().constrainBoundsRect_(proposedClipViewBoundsRect)
        view = self.documentView()
        viewFrame = view.frame()

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

        return rect
