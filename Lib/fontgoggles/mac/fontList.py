import AppKit
from vanilla import *
from fontTools.misc.arrayTools import offsetRect, scaleRect
from fontgoggles.mac.drawing import *
from fontgoggles.mac.misc import textAlignments
from fontgoggles.misc.decorators import suppressAndLogException
from fontgoggles.misc.properties import delegateProperty, hookedProperty
from fontgoggles.misc.rectTree import RectTree


class FGFontListView(AppKit.NSView):

    def acceptsFirstResponder(self):
        return True

    def becomeFirstResponder(self):
        return True

    def keyDown_(self, event):
        self.vanillaWrapper().keyDown(event)

    @suppressAndLogException
    def magnifyWithEvent_(self, event):
        pass
        # scrollView = self.enclosingScrollView()
        # clipView = scrollView.contentView()
        # if event.phase() == AppKit.NSEventPhaseBegan:
        #     self._savedClipBounds = clipView.bounds()
        # if event.phase() == AppKit.NSEventPhaseEnded:
        #     origin = clipView.bounds().origin
        #     fontList = self.vanillaWrapper()
        #     fontList.resizeFontItems(fontList.itemSize * scrollView.magnification())

        #     scrollView.setMagnification_(1.0)  #centeredAtPoint_
        #     # self._savedClipBounds.origin = clipView.bounds().origin
        #     bounds = clipView.bounds()
        #     bounds.origin = origin
        #     # clipView.setBounds_(bounds)
        #     del self._savedClipBounds
        # else:
        #     super().magnifyWithEvent_(event)


arrowKeyDefs = {
    AppKit.NSUpArrowFunctionKey: (-1, 1),
    AppKit.NSDownArrowFunctionKey: (1, 1),
    AppKit.NSLeftArrowFunctionKey: (-1, 0),
    AppKit.NSRightArrowFunctionKey: (1, 0),
}

fontItemIdentifierTemplate = "fontItem_{index}"


class FontList(Group):

    nsViewClass = FGFontListView

    def __init__(self, fontKeys, width, itemSize, selectionChangedCallback=None,
                 glyphSelectionChangedCallback=None):
        super().__init__((0, 0, width, 900))
        self._fontItemIdentifiers = []
        self._selection = set()  # a set of fontItemIdentifiers
        self.vertical = 0  # 0, 1: it is also an index into (x, y) tuples
        self.itemSize = itemSize
        self.align = "left"
        self._selectionChangedCallback = selectionChangedCallback
        self._glyphSelectionChangedCallback = glyphSelectionChangedCallback
        self.setupFontItems(fontKeys)

    def _glyphSelectionChanged(self):
        if self._glyphSelectionChangedCallback is not None:
            self._glyphSelectionChangedCallback(self)

    def setupFontItems(self, fontKeys):
        # clear all subviews
        for attr, value in list(self.__dict__.items()):
            if isinstance(value, VanillaBaseObject):
                delattr(self, attr)
        self._fontItemIdentifiers = []
        itemSize = self.itemSize
        y = 0
        for index, fontKey in enumerate(fontKeys):
            fontItemIdentifier = fontItemIdentifierTemplate.format(index=index)
            fontItem = FontItem((0, y, 0, itemSize), fontKey, fontItemIdentifier)
            setattr(self, fontItemIdentifier, fontItem)
            self._fontItemIdentifiers.append(fontItemIdentifier)
            y += itemSize
        self.setPosSize((0, 0, self.width, y))

    @property
    def width(self):
        return self.getPosSize()[2]

    @width.setter
    def width(self, newWidth):
        x, y, w, h = self.getPosSize()
        self.setPosSize((x, y, newWidth, h))

    @property
    def height(self):
        return self.getPosSize()[3]

    @height.setter
    def height(self, newHeight):
        x, y, w, h = self.getPosSize()
        self.setPosSize((x, y, w, newHeight))

    @hookedProperty
    def align(self):
        # self.align has already been set to the new value
        for fontItem in self.iterFontItems():
            fontItem.align = self.align

        scrollView = self._nsObject.enclosingScrollView()
        if scrollView is None:
            return

        ourBounds = self._nsObject.bounds()
        clipView = scrollView.contentView()
        clipBounds = clipView.bounds()
        if clipBounds.size.width >= ourBounds.size.width:
            # Handled by AligningScrollView
            return

        sizeDiff = ourBounds.size.width - clipBounds.size.width
        atLeft = abs(clipBounds.origin.x) < 2
        atRight = abs(clipBounds.origin.x - sizeDiff) < 2
        atCenter = abs(clipBounds.origin.x - sizeDiff / 2) < 2
        if self.align == "left":
            if atRight or atCenter:
                clipBounds.origin.x = 0
        elif self.align == "center":
            if atLeft or atRight:
                clipBounds.origin.x = sizeDiff / 2
        elif self.align == "right":
            if atLeft or atCenter:
                clipBounds.origin.x = sizeDiff
        clipView.setBounds_(clipBounds)

    def iterFontItems(self):
        for fontItemIdentifier in self._fontItemIdentifiers:
            yield self.getFontItem(fontItemIdentifier)

    @hookedProperty
    def vertical(self):
        # Note that we heavily depend on hookedProperty's property that
        # the hook is only called when the value is different than before.
        vertical = self.vertical
        pos = [0, 0]
        for fontItem in self.iterFontItems():
            fontItem.vertical = vertical
            fontItem.fileNameLabel.setPosSize(fontItem.getFileNameLabelPosSize())
            fontItem.fileNameLabel.rotate([-90, 90][vertical])
            x, y, w, h = fontItem.getPosSize()
            w, h = h, w
            fontItem.setPosSize((*pos, w, h))
            pos[1 - vertical] += self.itemSize
        x, y, w, h = self.getPosSize()
        w, h = h, w
        self.setPosSize((x, y, w, h))
        self._nsObject.setNeedsDisplay_(True)

    @suppressAndLogException
    def resizeFontItems(self, itemSize):
        scaleFactor = itemSize / self.itemSize
        self.itemSize = itemSize
        pos = [0, 0]
        for fontItem in self.iterFontItems():
            x, y, *wh = fontItem.getPosSize()
            wh[1 - self.vertical] = itemSize
            fontItem.setPosSize((*pos, *wh))
            pos[1 - self.vertical] += itemSize

        # calculate the center of our clip view in relative doc coords
        # so we can set the scroll position and zoom in/out "from the middle"
        x, y, w, h = self.getPosSize()
        clipView = self._nsObject.superview()
        (cx, cy), (cw, ch) = clipView.bounds()
        cx += cw / 2
        cy -= ch / 2
        cx /= w
        cy /= h

        if not self.vertical:
            self.setPosSize((x, y, w * scaleFactor, pos[1]))
            cx *= w * scaleFactor
            cy *= pos[1]
        else:
            self.setPosSize((x, y, pos[0], h * scaleFactor))
            cx *= pos[0]
            cy *= h * scaleFactor
        cx -= cw / 2
        cy += ch / 2
        clipBounds = clipView.bounds()
        clipBounds.origin = (cx, cy)
        clipView.setBounds_(clipBounds)

    @property
    def selection(self):
        return self._selection

    @selection.setter
    def selection(self, newSelection):
        diffSelection = self._selection ^ newSelection
        self._selection = newSelection
        for fontItemIdentifier in diffSelection:
            fontItem = self.getFontItem(fontItemIdentifier)
            fontItem.selected = not fontItem.selected
        if self._selectionChangedCallback is not None:
            self._selectionChangedCallback(self)

    def getFontItem(self, fontItemIdentifier):
        return getattr(self, fontItemIdentifier)

    def getNumFontItems(self):
        return len(self._fontItemIdentifiers)

    def getSingleSelectedItem(self):
        if len(self._fontItemIdentifiers) == 1:
            return self.getFontItem(self._fontItemIdentifiers[0])
        elif len(self.selection) == 1:
            return self.getFontItem(list(self.selection)[0])
        else:
            return None

    def _getSelectionRect(self, selection):
        selRect = None
        for fontItemIdentifier in selection:
            fontItem = self.getFontItem(fontItemIdentifier)
            if selRect is None:
                selRect = fontItem._nsObject.frame()
            else:
                selRect = AppKit.NSUnionRect(selRect, fontItem._nsObject.frame())
        return selRect

    def scrollSelectionToVisible(self, selection=None):
        if selection is None:
            selection = self._selection
        self._nsObject.scrollRectToVisible_(self._getSelectionRect(selection))

    def listItemMouseDown(self, event, fontItemIdentifier):
        if event.modifierFlags() & AppKit.NSCommandKeyMask:
            newSelection = self._selection ^ {fontItemIdentifier}
        elif fontItemIdentifier in self._selection:
            newSelection = None
        else:
            newSelection = {fontItemIdentifier}
        if newSelection is not None:
            self.selection = newSelection
            self.scrollSelectionToVisible({fontItemIdentifier})

    @suppressAndLogException
    def keyDown(self, event):
        chars = event.characters()
        if chars in arrowKeyDefs:
            direction, vertical = arrowKeyDefs[chars]
            if vertical == self.vertical:
                for ffi in self.selection:
                    fontItem = getattr(self, ffi)
                    fontItem.shiftSelectedGlyph(direction)
                return

            if not self._selection:
                if direction == 1:
                    self.selection = {self._fontItemIdentifiers[0]}
                else:
                    self.selection = {self._fontItemIdentifiers[-1]}
            else:
                indices = [i for i, fii in enumerate(self._fontItemIdentifiers) if fii in self._selection]
                if direction == 1:
                    index = min(len(self._fontItemIdentifiers) - 1, indices[-1] + 1)
                else:
                    index = max(0, indices[0] - 1)
                if event.modifierFlags() & AppKit.NSShiftKeyMask:
                    self.selection = self.selection | {self._fontItemIdentifiers[index]}
                else:
                    self.selection = {self._fontItemIdentifiers[index]}
                self.scrollSelectionToVisible()


class FontItem(Group):

    vertical = delegateProperty("glyphLineView")
    selected = delegateProperty("glyphLineView")

    def __init__(self, posSize, fontKey, fontItemIdentifier):
        super().__init__(posSize)
        # self._nsObject.setWantsLayer_(True)
        # self._nsObject.setCanDrawSubviewsIntoLayer_(True)
        self.fontItemIdentifier = fontItemIdentifier
        self.glyphLineView = GlyphLine((0, 0, 0, 0))
        self.fileNameLabel = UnclickableTextBox(self.getFileNameLabelPosSize(), "", sizeStyle="small")
        self.progressSpinner = ProgressSpinner((10, 20, 25, 25))
        self.setFontKey(fontKey)

    def setIsLoading(self, isLoading):
        if isLoading:
            self.progressSpinner.start()
        else:
            self.progressSpinner.stop()

    def setFontKey(self, fontKey):
        fontPath, fontNumber = fontKey
        fileNameLabel = f"{fontPath.name}"
        if fontNumber or fontPath.suffix.lower() in {".ttc", ".otc"}:
            fileNameLabel += f"#{fontNumber}"
        self.fileNameLabel.set(fileNameLabel, tooltip=str(fontPath))

    def setGlyphs(self, glyphs):
        self.glyphLineView._nsObject.setGlyphs_(glyphs)

    @property
    def glyphs(self):
        return self.glyphLineView._nsObject._glyphs

    @property
    def selection(self):
        return self.glyphLineView._nsObject.selection

    @selection.setter
    def selection(self, newSelection):
        self.glyphLineView._nsObject.selection = newSelection

    @property
    def minimumExtent(self):
        return self.glyphLineView._nsObject.minimumExtent

    @property
    def align(self):
        return self.glyphLineView._nsObject.align

    @align.setter
    def align(self, value):
        self.fileNameLabel.align = value
        self.glyphLineView._nsObject.align = value

    def getFileNameLabelPosSize(self):
        if self.vertical:
            return (2, 10, 17, -10)
        else:
            return (10, 0, -10, 17)

    def shiftSelectedGlyph(self, direction):
        self.glyphLineView._nsObject.shiftSelectedGlyph_(direction)


class FGGlyphLineView(AppKit.NSView):

    def _scheduleRedraw(self):
        self.setNeedsDisplay_(True)

    selected = hookedProperty(_scheduleRedraw)
    align = hookedProperty(_scheduleRedraw)

    def init(self):
        self = super().init()
        self.vertical = 0  # 0, 1: it will also be an index into (x, y) tuples
        self.selected = False
        self.align = "left"
        self._glyphs = None
        self._rectTree = None
        self._selection = set()
        return self

    def isOpaque(self):
        return True

    def acceptsFirstResponder(self):
        return True

    def becomeFirstResponder(self):
        # Defer to our FGFontListView
        fontListView = self.superview().superview()
        assert isinstance(fontListView, FGFontListView)
        return fontListView.becomeFirstResponder()

    def keyDown_(self, event):
        super().keyDown_(event)

    def shiftSelectedGlyph_(self, direction):
        index = None
        if direction == 1:
            if self._selection:
                index = min(len(self._glyphs) - 1, max(self._selection) + 1)
            elif self._glyphs:
                index = 0
        else:
            if self._selection:
                index = max(0, min(self._selection) - 1)
            elif self._glyphs:
                index = len(self._glyphs) - 1
        if index is not None:
            self.selection = {index}

    @property
    def selection(self):
        return self._selection

    @selection.setter
    def selection(self, newSelection):
        diffSelection = self._selection ^ newSelection
        self._selection = newSelection
        dx, dy = self.origin
        scaleFactor = self.scaleFactor
        for index in diffSelection:
            bounds = self._glyphs[index].bounds
            if bounds is None:
                continue
            bounds = offsetRect(scaleRect(bounds, scaleFactor, scaleFactor), dx, dy)
            self.setNeedsDisplayInRect_(nsRectFromRect(bounds))
        if diffSelection:
            fontList = self.superview().superview().vanillaWrapper()
            fontList._glyphSelectionChanged()

    def setGlyphs_(self, glyphs):
        self._glyphs = glyphs
        rectIndexList = [(gi.bounds, index) for index, gi in enumerate(glyphs) if gi.bounds is not None]
        self._rectTree = RectTree.fromSeq(rectIndexList)
        self._selection = set()
        self.setNeedsDisplay_(True)

    @property
    def minimumExtent(self):
        if self._glyphs is None:
            return self.margin * 2
        else:
            return self.margin * 2 + abs(self._glyphs.endPos[self.vertical]) * self.scaleFactor

    @property
    def scaleFactor(self):
        itemSize = self.frame().size[1 - self.vertical]
        return 0.7 * itemSize / self._glyphs.unitsPerEm

    @property
    def margin(self):
        itemSize = self.frame().size[1 - self.vertical]
        return 0.1 * itemSize

    @property
    def origin(self):
        endPos = abs(self._glyphs.endPos[self.vertical]) * self.scaleFactor
        margin = self.margin
        align = self.align
        itemExtent = self.frame().size[self.vertical]
        itemSize = self.frame().size[1 - self.vertical]
        if align == "right" or align == "bottom":
            pos = itemExtent - margin - endPos
        elif align == "center":
            pos = (itemExtent - endPos) / 2
        else:  # align == "left" or align == "top"
            pos = margin
        if not self.vertical:
            return pos, 0.25 * itemSize  # TODO: something with hhea/OS/2 ascender/descender
        else:
            return 0.5 * itemSize, itemExtent - pos  # TODO: something with vhea ascender/descender

    @suppressAndLogException
    def drawRect_(self, rect):
        backgroundColor = AppKit.NSColor.textBackgroundColor()
        foregroundColor = AppKit.NSColor.textColor()

        if self.selected:
            # Blend color could be a pref from the systemXxxxColor colors
            backgroundColor = backgroundColor.blendedColorWithFraction_ofColor_(0.5, AppKit.NSColor.selectedTextBackgroundColor())

        selection = self._selection if self.selected else ()
        if selection:
            selectedColor = foregroundColor.blendedColorWithFraction_ofColor_(0.9, AppKit.NSColor.systemRedColor())

        backgroundColor.set()
        AppKit.NSRectFill(rect)

        if not self._glyphs:
            return

        dx, dy = self.origin

        invScale = 1 / self.scaleFactor
        rect = rectFromNSRect(rect)
        rect = scaleRect(offsetRect(rect, -dx, -dy), invScale, invScale)

        translate(dx, dy)
        scale(self.scaleFactor)

        foregroundColor.set()
        lastPosX = lastPosY = 0
        for index in self._rectTree.iterIntersections(rect):
            gi = self._glyphs[index]
            selected = index in selection
            if selected:
                selectedColor.set()
            posX, posY = gi.pos
            translate(posX - lastPosX, posY - lastPosY)
            lastPosX, lastPosY = posX, posY
            gi.path.fill()
            if selected:
                AppKit.NSColor.textColor().set()

    @suppressAndLogException
    def mouseDown_(self, event):
        if self._rectTree is None:
            return
        x, y = self.convertPoint_fromView_(event.locationInWindow(), None)
        scaleFactor = self.scaleFactor
        dx, dy = self.origin
        x -= dx
        y -= dy
        x /= scaleFactor
        y /= scaleFactor

        indices = list(self._rectTree.iterIntersections((x, y, x, y)))
        if not indices:
            index = None
        elif len(indices) == 1:
            index = indices[0]
        else:
            # There are multiple candidates. Let's do point-inside testing,
            # and take the last hit, if any. Fall back to the last.
            for index in reversed(indices):
                gi = self._glyphs[index]
                posX, posY = gi.pos
                if gi.path.containsPoint_((x - posX, y - posY)):
                    break
            else:
                index = indices[-1]

        if index is not None:
            if self._selection is None:
                self._selection = set()
            newSelection = {index}
            if newSelection == self._selection:
                newSelection = set()  # deselect
            self.selection = newSelection

        fontItemIdentifier = self.superview().vanillaWrapper().fontItemIdentifier
        fontList = self.superview().superview().vanillaWrapper()
        fontList.listItemMouseDown(event, fontItemIdentifier)


class GlyphLine(Group):
    nsViewClass = FGGlyphLineView
    vertical = delegateProperty("_nsObject")
    selected = delegateProperty("_nsObject")


class FGUnclickableTextField(AppKit.NSTextField):

    def hitTest_(self, point):
        return None


class UnclickableTextBox(TextBox):

    """This TextBox sublass is transparent for clicks."""

    nsTextFieldClass = FGUnclickableTextField

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._nsObject.cell().setLineBreakMode_(AppKit.NSLineBreakByTruncatingMiddle)

    def set(self, value, tooltip=None):
        super().set(value)
        if tooltip is not None:
            self._nsObject.setToolTip_(tooltip)

    def rotate(self, angle):
        self._nsObject.rotateByAngle_(angle)

    @property
    def align(self):
        return self._nsObject.alignment()

    @align.setter
    def align(self, value):
        nsAlignment = textAlignments.get(value, textAlignments["left"])
        self._nsObject.cell().setAlignment_(nsAlignment)
