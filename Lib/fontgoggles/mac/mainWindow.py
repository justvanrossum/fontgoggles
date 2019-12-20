import asyncio
import unicodedata
import time
import AppKit
import objc
from vanilla import *
from fontTools.misc.arrayTools import offsetRect, scaleRect
from fontgoggles.mac.aligningScrollView import AligningScrollView
from fontgoggles.mac.drawing import *
from fontgoggles.mac.misc import ClassNameIncrementer, makeTextCell, _textAlignments as textAlignments
from fontgoggles.misc.decorators import (asyncTaskAutoCancel, suppressAndLogException,
                                         hookedProperty)
from fontgoggles.misc.rectTree import RectTree
from fontgoggles.misc.textInfo import TextInfo


class FGGlyphLineView(AppKit.NSView, metaclass=ClassNameIncrementer):

    _glyphs = None
    _rectTree = None
    _selection = None
    _endPos = (0, 0)

    def init(self):
        self = super().init()
        self.align = "left"
        self.unitsPerEm = 1000  # We need a non-zero default, proper value will be set later
        return self

    def isOpaque(self):
        return True

    def setGlyphs_endPos_upm_(self, glyphs, endPos, unitsPerEm):
        self._glyphs = glyphs
        self._endPos = endPos
        self.unitsPerEm = unitsPerEm
        rectIndexList = [(gi.bounds, index) for index, gi in enumerate(glyphs) if gi.bounds is not None]
        self._rectTree = RectTree.fromSeq(rectIndexList)
        self._selection = set()
        self.setNeedsDisplay_(True)
        # Return the minimal width our view must have to fit the glyphs
        return self.margin * 2 + endPos[0] * self.scaleFactor

    @property
    def minimumWidth(self):
        return self.margin * 2 + self._endPos[0] * self.scaleFactor

    @hookedProperty
    def align(self):
        self.setNeedsDisplay_(True)

    @property
    def scaleFactor(self):
        height = self.frame().size.height
        return 0.7 * height / self.unitsPerEm

    @property
    def margin(self):
        height = self.frame().size.height
        return 0.1 * height

    @property
    def origin(self):
        endPosX = self._endPos[0] * self.scaleFactor
        margin = self.margin
        align = self.align
        width, height = self.frame().size
        if align == "right":
            xPos = width - margin - endPosX
        elif align == "center":
            xPos = (width - endPosX) / 2
        else:  # align == "left"
            xPos = margin
        return xPos, 0.25 * height

    @suppressAndLogException
    def drawRect_(self, rect):
        AppKit.NSColor.whiteColor().set()
        AppKit.NSRectFill(rect)

        if not self._glyphs:
            return

        dx, dy = self.origin

        invScale = 1 / self.scaleFactor
        rect = rectFromNSRect(rect)
        rect = scaleRect(offsetRect(rect, -dx, -dy), invScale, invScale)

        translate(dx, dy)
        scale(self.scaleFactor)

        AppKit.NSColor.blackColor().set()
        lastPosX = lastPosY = 0
        for index in self._rectTree.iterIntersections(rect):
            gi = self._glyphs[index]
            selected = self._selection and index in self._selection
            if selected:
                AppKit.NSColor.redColor().set()
            posX, posY = gi.pos
            translate(posX - lastPosX, posY - lastPosY)
            lastPosX, lastPosY = posX, posY
            gi.path.fill()
            if selected:
                AppKit.NSColor.blackColor().set()

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
            return
        if len(indices) == 1:
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
            diffSelection = self._selection ^ newSelection
            self._selection = newSelection
            for index in diffSelection:
                bounds = self._glyphs[index].bounds
                if bounds is None:
                    continue
                bounds = offsetRect(scaleRect(bounds, scaleFactor, scaleFactor), dx, dy)
                self.setNeedsDisplayInRect_(nsRectFromRect(bounds))


class FGFontListView(AppKit.NSView, metaclass=ClassNameIncrementer):

    @suppressAndLogException
    def magnifyWithEvent_(self, event):
        print(self, self.vanillaWrapper(), event)


class GlyphLine(Group):
    nsViewClass = FGGlyphLineView


fontItemNameTemplate = "fontItem_{index}"


class FontList(Group):

    nsViewClass = FGFontListView

    def __init__(self, fontKeys, width, itemHeight):
        super().__init__((0, 0, width, 900))
        self.align = "left"
        y = 0
        for index, fontKey in enumerate(fontKeys):
            fontItemName = fontItemNameTemplate.format(index=index)
            fontItem = FontItem((0, y, 0, itemHeight), fontKey)
            setattr(self, fontItemName, fontItem)
            y += itemHeight
        self.setPosSize((0, 0, width, y))

    @property
    def width(self):
        return self.getPosSize()[2]

    @width.setter
    def width(self, newWidth):
        oldWidth = self._nsObject.bounds().size.width
        x, y, w, h = self.getPosSize()
        self.setPosSize((x, y, newWidth, h))

    @property
    def height(self):
        return self.getPosSize()[3]

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
        index = 0
        while True:
            item = getattr(self, fontItemNameTemplate.format(index=index), None)
            if item is None:
                break
            yield item
            index += 1

    def resizeFontItems(self, itemHeight):
        posY = 0
        for fontItem in self.iterFontItems():
            x, y, w, h = fontItem.getPosSize()
            fontItem.setPosSize((x, posY, w, itemHeight))
            posY += itemHeight
        x, y, w, h = self.getPosSize()
        self.setPosSize((x, y, w, posY))


class FontItem(Group):

    def __init__(self, posSize, fontKey):
        super().__init__(posSize)
        self.glyphLineView = GlyphLine((0, 0, 0, 0))
        self.fileNameLabel = TextBox((10, 0, -10, 17), "", sizeStyle="regular")
        self.fileNameLabel._nsObject.cell().setLineBreakMode_(AppKit.NSLineBreakByTruncatingMiddle)
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
        if fontNumber:
            fileNameLabel += f"#{fontNumber}"
        self.fileNameLabel.set(fileNameLabel)
        self.fileNameLabel._nsObject.setToolTip_(str(fontPath))

    def setGlyphs(self, glyphs, endPos, unitsPerEm):
        self.glyphLineView._nsObject.setGlyphs_endPos_upm_(glyphs, endPos, unitsPerEm)

    @property
    def minimumWidth(self):
        return self.glyphLineView._nsObject.minimumWidth

    @property
    def align(self):
        return self.glyphLineView._nsObject.align

    @align.setter
    def align(self, value):
        self.fileNameLabel._nsObject.cell().setAlignment_(textAlignments[value])
        self.glyphLineView._nsObject.align = value


# When the size of the line view needs to grow, overallocate this amount,
# to avoid having to resize the font line group too often. In other words,
# this value specifies some wiggle room: the font list can be a little
# larger than strictly necessary for fitting all glyphs.
groupsSizePadding = 200


directionPopUpConfig = [
    ("Automatic, with BiDi", None),
    ("Automatic, without BiDi", None),
    ("Left-to-Right", "LTR"),
    ("Right-to-Left", "RTL"),
    ("Top-to-Bottom", "TTB"),
    ("Bottom-to-Top", "BTT"),
]
directionOptions = [label for label, direction in directionPopUpConfig]
directionSettings = [direction for label, direction in directionPopUpConfig]


class FGMainWindowController(AppKit.NSWindowController, metaclass=ClassNameIncrementer):

    def __new__(cls, project):
        return cls.alloc().init()

    def __init__(self, project):
        self.project = project
        self.fontKeys = list(self.project.iterFontKeys())
        self.allFeatureTags = set()
        self.itemHeight = 150

        sidebarWidth = 300

        unicodeListGroup = self.setupUnicodeListGroup()
        glyphListGroup = self.setupGlyphListGroup()
        fontListGroup = self.setupFontListGroup()
        sidebarGroup = self.setupSidebarGroup()

        paneDescriptors = [
            dict(view=glyphListGroup, identifier="glyphList", canCollapse=True,
                 size=205, resizeFlexibility=False),
            dict(view=fontListGroup, identifier="fontList", canCollapse=False,
                 size=200),
        ]
        subSplitView = SplitView((0, 0, 0, 0), paneDescriptors, dividerStyle="thin")
        self.subSplitView = subSplitView

        paneDescriptors = [
            dict(view=unicodeListGroup, identifier="characterList", canCollapse=True,
                 size=100, minSize=100, resizeFlexibility=False),
            dict(view=subSplitView, identifier="subSplit", canCollapse=False),
            dict(view=sidebarGroup, identifier="formattingOptions", canCollapse=True,
                 size=sidebarWidth, minSize=sidebarWidth, maxSize=sidebarWidth,
                 resizeFlexibility=False),
        ]
        mainSplitView = SplitView((0, 0, 0, 0), paneDescriptors, dividerStyle="thin")

        self.w = Window((800, 500), "FontGoggles", minSize=(200, 500), autosaveName="FontGogglesWindow")
        self.w.mainSplitView = mainSplitView
        self.w.open()
        self.w._window.setWindowController_(self)
        self.w._window.makeFirstResponder_(fontListGroup.textEntry._nsObject)

        initialText = "ABC abc 0123 :;?"
        self._textEntry.set(initialText)
        self.textEntryChangedCallback(self._textEntry)

        self.loadFonts()

    @objc.python_method
    def setupUnicodeListGroup(self):
        group = Group((0, 0, 0, 0))
        columnDescriptions = [
            # dict(title="index", width=34, cell=makeTextCell("right")),
            dict(title="char", width=30, typingSensitive=True, cell=makeTextCell("center")),
            dict(title="unicode", width=60, cell=makeTextCell("right")),
            dict(title="unicode name", width=200, minWidth=200, key="unicodeName",
                 cell=makeTextCell("left", "truncmiddle")),
        ]
        self.unicodeList = List((0, 40, 0, 0), [],
                                columnDescriptions=columnDescriptions,
                                allowsSorting=False, drawFocusRing=False, rowHeight=20)
        self.unicodeShowBiDiCheckBox = CheckBox((10, 8, -10, 20), "BiDi",
                                                callback=self.unicodeShowBiDiCheckBoxCallback)
        group.unicodeShowBiDiCheckBox = self.unicodeShowBiDiCheckBox
        group.unicodeList = self.unicodeList
        return group

    @objc.python_method
    def setupGlyphListGroup(self):
        group = Group((0, 0, 0, 0))
        columnDescriptions = [
            # dict(title="index", width=34, cell=makeTextCell("right")),
            dict(title="glyph", key="name", width=70, minWidth=70, maxWidth=200,
                 typingSensitive=True, cell=makeTextCell("left", lineBreakMode="truncmiddle")),
            dict(title="adv", key="ax", width=40, cell=makeTextCell("right")),  # XXX
            dict(title="∆X", key="dx", width=40, cell=makeTextCell("right")),
            dict(title="∆Y", key="dy", width=40, cell=makeTextCell("right")),
            dict(title="cluster", width=40, cell=makeTextCell("right")),
            dict(title="gid", width=40, cell=makeTextCell("right")),
            # dummy filler column so "glyph" doesn't get to wide:
            dict(title="", key="_dummy_", minWidth=0, maxWidth=1400),
        ]
        self.glyphList = List((0, 40, 0, 0), [],
                              columnDescriptions=columnDescriptions,
                              allowsSorting=False, drawFocusRing=False,
                              rowHeight=20)
        group.glyphList = self.glyphList
        return group

    @objc.python_method
    def setupFontListGroup(self):
        group = Group((0, 0, 0, 0))
        self._textEntry = EditText((10, 8, -10, 25), "", callback=self.textEntryChangedCallback)
        self._fontList = FontList(self.fontKeys, 300, self.itemHeight)
        self._fontListScrollView = AligningScrollView((0, 40, 0, 0), self._fontList, drawBackground=True)
        group.fontList = self._fontListScrollView
        group.textEntry = self._textEntry
        return group

    @objc.python_method
    def setupSidebarGroup(self):
        group = Group((0, 0, 0, 0))
        group.generalSettings = self.setupGeneralSettingsGroup()
        x, y, w, h = group.generalSettings.getPosSize()
        group.feaVarTabs = Tabs((0, h + 6, 0, 0), ["Features", "Variations", "Options"])
        return group

    def setupGeneralSettingsGroup(self):
        group = Group((0, 0, 0, 0))
        y = 10
        self.directionPopUp = LabeledView(
            (10, y, -10, 40), "Direction/orientation:",
            PopUpButton, directionOptions,
            callback=self.directionPopUpCallback,
        )
        group.directionPopUp = self.directionPopUp
        y += 50
        alignmentOptionsHorizontal = [
            "Automatic",
            "Left",   # Top
            "Right",  # Bottom
            "Center",
        ]
        group.alignmentPopup = LabeledView(
            (10, y, -10, 40), "Visual alignment:",
            PopUpButton, alignmentOptionsHorizontal,
            callback=self.alignmentChangedCallback,
        )
        y += 50
        group.setPosSize((0, 0, 0, y))
        return group

    def loadFonts(self):
        self._startLoading = time.time()
        self._loadCounter = 0
        sharableFontData = {}
        firstKey = self.fontKeys[0] if self.fontKeys else None
        for fontKey, fontItem in zip(self.fontKeys, self.iterFontItems()):
            isSelectedFont = (fontKey == firstKey)
            coro = self._loadFont(fontKey, fontItem, sharableFontData=sharableFontData,
                                  isSelectedFont=isSelectedFont)
            asyncio.create_task(coro)

    @objc.python_method
    async def _loadFont(self, fontKey, fontItem, sharableFontData, isSelectedFont):
        # print(f"start loading at {time.time() - self._startLoading:.4f} seconds")
        fontItem.setIsLoading(True)
        fontPath, fontNumber = fontKey
        await self.project.loadFont(fontPath, fontNumber, sharableFontData=sharableFontData)
        font = self.project.getFont(fontPath, fontNumber)
        self._loadCounter += 1
        # print(f"loaded {self._loadCounter} fonts in {time.time() - self._startLoading:.4f} seconds")
        await asyncio.sleep(0)
        fontItem.setIsLoading(False)
        self.allFeatureTags.update(font.features)
        self.setFontItemText(fontKey, fontItem, isSelectedFont)

    def iterFontItems(self):
        return self._fontList.iterFontItems()

    @objc.python_method
    def unicodeShowBiDiCheckBoxCallback(self, sender):
        self.updateUnicodeList()

    @objc.python_method
    def directionPopUpCallback(self, sender):
        self.textEntryChangedCallback(self._textEntry)

    @asyncTaskAutoCancel
    async def textEntryChangedCallback(self, sender):
        self.textInfo = TextInfo(sender.get())
        self.textInfo.shouldApplyBiDi = self.directionPopUp.get() == 0

        align = self.textInfo.suggestedAlignment

        self.updateUnicodeList(delay=0.05)
        t = time.time()
        firstKey = self.fontKeys[0] if self.fontKeys else None
        for fontKey, fontItem in zip(self.fontKeys, self.iterFontItems()):
            isSelectedFont = (fontKey == firstKey)
            self.setFontItemText(fontKey, fontItem, isSelectedFont=isSelectedFont)
            elapsed = time.time() - t
            if elapsed > 0.01:
                # time to unblock the event loop
                await asyncio.sleep(0)
                t = time.time()
        newWidth = 300  # some minimum so that our filename label stays large enough
        for fontItem in self.iterFontItems():
            newWidth = max(newWidth, fontItem.minimumWidth)
        if self._fontList.width > newWidth + groupsSizePadding:
            # Shrink the font list
            self._fontList.width = newWidth
            # TODO: deal with scroll position

    @objc.python_method
    def setFontItemText(self, fontKey, fontItem, isSelectedFont):
        fontPath, fontNumber = fontKey
        font = self.project.getFont(fontPath, fontNumber, None)
        if font is None:
            return
        glyphs, endPos = getGlyphRun(font, self.textInfo.text,
                                     direction=self.textInfo.directionForShaper)
        if isSelectedFont:
            self.updateGlyphList(glyphs, delay=0.05)
        fontItem.setGlyphs(glyphs, endPos, font.unitsPerEm)
        minimumWidth = fontItem.minimumWidth
        if minimumWidth > self._fontList.width:
            # We make it a little wider than needed, so as to minimize the
            # number of times we need to make it grow, as it requires a full
            # redraw.
            self._fontList.width = minimumWidth + groupsSizePadding
            # TODO: deal with scroll position

    @asyncTaskAutoCancel
    async def updateGlyphList(self, glyphs, delay=0):
        if delay:
            # add a slight delay, so we won't do a lot of work when there's fast typing
            await asyncio.sleep(delay)
        glyphListData = [g.__dict__ for g in glyphs]
        self.glyphList.set(glyphListData)

    @asyncTaskAutoCancel
    async def updateUnicodeList(self, delay=0):
        if delay:
            # add a slight delay, so we won't do a lot of work when there's fast typing
            await asyncio.sleep(delay)
        if self.unicodeShowBiDiCheckBox.get():
            txt = self.textInfo.text
        else:
            txt = self.textInfo.originalText
        uniListData = []
        for index, char in enumerate(txt):
            uniListData.append(
                dict(index=index, char=char, unicode=f"U+{ord(char):04X}",
                     unicodeName=unicodedata.name(char, "?"))
            )
        self.unicodeList.set(uniListData)

    @suppressAndLogException
    def alignmentChangedCallback(self, sender):
        values = [None, "left", "right", "center"]
        align = values[sender.get()]
        if align:
            self._fontList.align = align
            self._fontListScrollView.hAlign = align

    def showCharacterList_(self, sender):
        self.w.mainSplitView.togglePane("characterList")

    def showGlyphList_(self, sender):
        self.subSplitView.togglePane("glyphList")

    def showFormattingOptions_(self, sender):
        self.w.mainSplitView.togglePane("formattingOptions")

    @suppressAndLogException
    def validateMenuItem_(self, sender):
        action = sender.action()
        title = sender.title()
        isVisible = None
        findReplace = ["Hide", "Show"]
        if action == "showCharacterList:":
            isVisible = not self.w.mainSplitView.isPaneVisible("characterList")
        elif action == "showGlyphList:":
            isVisible = not self.subSplitView.isPaneVisible("glyphList")
        elif action == "showFormattingOptions:":
            isVisible = not self.w.mainSplitView.isPaneVisible("formattingOptions")
        if isVisible is not None:
            if isVisible:
                findReplace.reverse()
            newTitle = title.replace(findReplace[0], findReplace[1])
            sender.setTitle_(newTitle)
        return True

    def zoomIn_(self, sender):
        self.itemHeight = min(1000, round(self.itemHeight * (2 ** (1 / 3))))
        self._fontList.resizeFontItems(self.itemHeight)

    def zoomOut_(self, sender):
        self.itemHeight = max(50, round(self.itemHeight / (2 ** (1 / 3))))
        self._fontList.resizeFontItems(self.itemHeight)


class LabeledView(Group):

    def __init__(self, posSize, label, viewClass, *args, **kwargs):
        super().__init__(posSize)
        x, y, w, h = posSize
        assert h > 0
        self.label = TextBox((0, 0, 0, 0), label)
        self.view = viewClass((0, 20, 0, 20), *args, **kwargs)

    def get(self):
        return self.view.get()


def getGlyphRun(font, txt, **kwargs):
    glyphs = font.getGlyphRun(txt, **kwargs)
    x = y = 0
    for gi in glyphs:
        gi.pos = posX, posY = x + gi.dx, y + gi.dy
        if gi.path.elementCount():
            gi.bounds = offsetRect(rectFromNSRect(gi.path.controlPointBounds()), posX, posY)
        else:
            gi.bounds = None
        x += gi.ax
        y += gi.ay
    return glyphs, (x, y)
