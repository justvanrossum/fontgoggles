import asyncio
import contextlib
import pathlib
import unicodedata
import time
import AppKit
import objc
from vanilla import *
from fontTools.misc.arrayTools import offsetRect, scaleRect
from fontgoggles.font import getOpener
from fontgoggles.project import Project
from fontgoggles.mac.aligningScrollView import AligningScrollView
from fontgoggles.mac.drawing import *
from fontgoggles.mac.misc import ClassNameIncrementer, makeTextCell
from fontgoggles.misc.decorators import asyncTask, asyncTaskAutoCancel, suppressAndLogException
from fontgoggles.misc.rectTree import RectTree


class FGGlyphLineView(AppKit.NSView, metaclass=ClassNameIncrementer):

    _glyphs = None
    _rectTree = None
    _selection = None

    def isOpaque(self):
        return True

    def setGlyphs_endPos_upm_(self, glyphs, endPos, unitsPerEm):
        self._glyphs = glyphs
        self.unitsPerEm = unitsPerEm
        x = y = 0
        rectIndexList = [(gi.bounds, index) for index, gi in enumerate(glyphs) if gi.bounds is not None]
        self._rectTree = RectTree.fromSeq(rectIndexList)
        self._selection = set()
        self.setNeedsDisplay_(True)

    @suppressAndLogException
    def mouseDown_(self, event):
        if self._rectTree is None:
            return
        x, y = self.convertPoint_fromView_(event.locationInWindow(), None)
        scaleFactor = self.scaleFactor
        dx, dy = self.offset
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

    @property
    def scaleFactor(self):
        height = self.frame().size.height
        return 0.7 * height / self.unitsPerEm

    @property
    def offset(self):
        height = self.frame().size.height
        return 10, 0.25 * height

    @suppressAndLogException
    def drawRect_(self, rect):
        AppKit.NSColor.whiteColor().set()
        AppKit.NSRectFill(rect)

        if not self._glyphs:
            return

        dx, dy = self.offset

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


class FGFontGroupView(AppKit.NSView, metaclass=ClassNameIncrementer):

    @suppressAndLogException
    def magnifyWithEvent_(self, event):
        print(self, self.vanillaWrapper(), event)


class GlyphLine(Group):
    nsViewClass = FGGlyphLineView


fontItemNameTemplate = "fontItem_{index}"


class FontGroup(Group):

    nsViewClass = FGFontGroupView

    def __init__(self, fontKeys, width, itemHeight):
        super().__init__((0, 0, width, 900))
        y = 0
        for index, fontKey in enumerate(fontKeys):
            fontItemName = fontItemNameTemplate.format(index=index)
            fontItem = FontItem((0, y, 0, itemHeight), fontKey)
            setattr(self, fontItemName, fontItem)
            y += itemHeight
        self.setPosSize((0, 0, width, y))

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
        self.fileNameLabel = TextBox((10, 0, 300, 17), "", sizeStyle="regular")
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


class FGMainWindowController(AppKit.NSWindowController, metaclass=ClassNameIncrementer):

    def __new__(cls, project):
        return cls.alloc().init()

    def __init__(self, project):
        self.project = project
        self.fontKeys = list(self.project.iterFontKeys())
        self.itemHeight = 150

        sidebarWidth = 300

        unicodeListGroup = self.setupUnicodeListGroup()
        glyphListGroup = self.setupGlyphListGroup()
        fontListGroup = self.setupFontListGroup()
        sidebarGroup = self.setupSidebarGroup()

        paneDescriptors = [
            dict(view=glyphListGroup, identifier="pane1", canCollapse=True,
                 size=205, resizeFlexibility=False),
            dict(view=fontListGroup, identifier="pane2", canCollapse=False,
                 size=200),
        ]
        subSplitView = SplitView((0, 0, 0, 0), paneDescriptors, dividerStyle="thin")

        paneDescriptors = [
            dict(view=unicodeListGroup, identifier="pane1", canCollapse=True,
                 size=100, resizeFlexibility=False),
            dict(view=subSplitView, identifier="pane3", canCollapse=False),
            dict(view=sidebarGroup, identifier="pane4", canCollapse=True,
                size=sidebarWidth, minSize=sidebarWidth, maxSize=sidebarWidth, resizeFlexibility=False),
        ]
        mainSplitView = SplitView((0, 0, 0, 0), paneDescriptors, dividerStyle="thin")

        self.w = Window((800, 500), "FontGoggles", minSize=(200, 500), autosaveName="FontGogglesWindow")
        self.w.mainSplitView = mainSplitView
        self.w.open()
        self.w._window.setWindowController_(self)
        self.w._window.makeFirstResponder_(fontListGroup.textEntry._nsObject)
        self.updateUnicodeList(self._textEntry.get())
        self.loadFonts()

    @objc.python_method
    def setupUnicodeListGroup(self):
        group = Group((0, 0, 0, 0))
        columnDescriptions = [
            # dict(title="index", width=34, cell=makeTextCell("right")),
            dict(title="char", width=30, typingSensitive=True, cell=makeTextCell("center")),
            dict(title="unicode", width=60, cell=makeTextCell("right")),
            dict(title="unicode name", width=200, minWidth=200, key="unicodeName", cell=makeTextCell("left", "truncmiddle")),
        ]
        self.unicodeList = List((0, 40, 0, 0), [],
                columnDescriptions=columnDescriptions,
                allowsSorting=False, drawFocusRing=False, rowHeight=20)
        group.bidiCheckBox = CheckBox((10, 8, -10, 20), "BiDi")
        group.unicodeList = self.unicodeList
        return group

    @objc.python_method
    def setupGlyphListGroup(self):
        group = Group((0, 0, 0, 0))
        columnDescriptions = [
            # dict(title="index", width=34, cell=makeTextCell("right")),
            dict(title="glyph", key="name", width=70, minWidth=70, maxWidth=200, typingSensitive=True, cell=makeTextCell("left", lineBreakMode="truncmiddle")),
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
                allowsSorting=False, drawFocusRing=False, rowHeight=20)
        group.glyphList = self.glyphList
        return group

    @objc.python_method
    def setupFontListGroup(self):
        group = Group((0, 0, 0, 0))
        initialText = "ABC abc 0123 :;?"
        self._textEntry = EditText((10, 8, -10, 25), initialText, callback=self.textEntryCallback)
        self._fontGroup = FontGroup(self.fontKeys, 3000, self.itemHeight)
        group.fontList = AligningScrollView((0, 40, 0, 0), self._fontGroup, drawBackground=True)
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
        directionOptions = [
            "Automatic, with BiDi",
            "Automatic, without BiDi",
            "Left-to-Right",
            "Right-to-Left",
            "Top-to-Bottom",
            "Bottom-to-Top",
        ]
        group.directionPopUp = LabeledView(
            (10, y, -10, 40), "Direction/orientation:",
            PopUpButton, directionOptions,
        )
        y += 50
        alignmentOptionsHorizontal = [
            "Automatic",
            "Left", # Top
            "Right", # Bottom
            "Center",
        ]
        group.alignmentPopup = LabeledView(
            (10, y, -10, 40), "Visual alignment:",
            PopUpButton, alignmentOptionsHorizontal,
        )
        y += 50
        group.setPosSize((0, 0, 0, y))
        return group

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
        txt = self._textEntry.get()
        self.setFontItemText(fontKey, fontItem, txt, isSelectedFont)

    def loadFonts(self):
        self._startLoading = time.time()
        self._loadCounter = 0
        sharableFontData = {}
        firstKey = self.fontKeys[0] if self.fontKeys else None
        for fontKey, fontItem in zip(self.fontKeys, self.iterFontItems()):
            coro = self._loadFont(fontKey, fontItem, sharableFontData=sharableFontData,
                                  isSelectedFont=fontKey==firstKey)
            asyncio.create_task(coro)

    def iterFontItems(self):
        return self._fontGroup.iterFontItems()

    @asyncTaskAutoCancel
    async def textEntryCallback(self, sender):
        txt = sender.get()
        self.updateUnicodeList(txt, delay=0.05)
        t = time.time()
        firstKey = self.fontKeys[0] if self.fontKeys else None
        for fontKey, fontItem in zip(self.fontKeys, self.iterFontItems()):
            self.setFontItemText(fontKey, fontItem, txt, fontKey==firstKey)
            elapsed = time.time() - t
            if elapsed > 0.01:
                # time to unblock the event loop
                await asyncio.sleep(0)
                t = time.time()

    @objc.python_method
    def setFontItemText(self, fontKey, fontItem, txt, isSelectedFont):
        fontPath, fontNumber = fontKey
        font = self.project.getFont(fontPath, fontNumber, None)
        if font is None:
            return
        glyphs, endPos = getGlyphRun(font, txt)
        if isSelectedFont:
            self.updateGlyphList(glyphs, delay=0.05)
        fontItem.setGlyphs(glyphs, endPos, font.unitsPerEm)

    @asyncTaskAutoCancel
    async def updateGlyphList(self, glyphs, delay=0):
        if delay:
            # add a slight delay, so we won't do a lot of work when there's fast typing
            await asyncio.sleep(delay)
        glyphListData = [g.__dict__ for g in glyphs]
        self.glyphList.set(glyphListData)

    @asyncTaskAutoCancel
    async def updateUnicodeList(self, txt, delay=0):
        if delay:
            # add a slight delay, so we won't do a lot of work when there's fast typing
            await asyncio.sleep(delay)
        uniListData = []
        for index, char in enumerate(txt):
            uniListData.append(
                dict(index=index, char=char, unicode=f"U+{ord(char):04X}",
                     unicodeName=unicodedata.name(char, "?"))
            )
        self.unicodeList.set(uniListData)

    def zoomIn_(self, event):
        self.itemHeight = min(1000, round(self.itemHeight * (2 ** (1/3))))
        self._fontGroup.resizeFontItems(self.itemHeight)

    def zoomOut_(self, event):
        self.itemHeight = max(50, round(self.itemHeight / (2 ** (1/3))))
        self._fontGroup.resizeFontItems(self.itemHeight)


class LabeledView(Group):

    def __init__(self, posSize, label, viewClass, *args, **kwargs):
        super().__init__(posSize)
        x, y, w, h = posSize
        assert h > 0
        self.label = TextBox((0, 0, 0, 0), label)
        self.view = viewClass((0, 20, 0, 20), *args, **kwargs)


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


if __name__ == "__main__":
    proj = Project()
    paths = [
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Italic.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Bold.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-ExtraLight.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Light.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Medium.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Regular.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-SemiBold.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Text.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Thin.ttf',
        # '/Users/just/code/git/fontgoggles/Tests/data/MutatorSansBoldWide.ufo',
    ]

    plex = [
        '/Users/just/code/git/ibm_plex/IBM-Plex-Sans-Variable/sources/IBM Plex Sans Var-Bold Condensed Italic.ufo',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Sans-Variable/sources/IBM Plex Sans Var-Bold Condensed.ufo',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Sans-Variable/sources/IBM Plex Sans Var-Bold Italic.ufo',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Sans-Variable/sources/IBM Plex Sans Var-Bold.ufo',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Sans-Variable/sources/IBM Plex Sans Var-Condensed Italic.ufo',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Sans-Variable/sources/IBM Plex Sans Var-Condensed.ufo',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Sans-Variable/sources/IBM Plex Sans Var-Italic.ufo',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Sans-Variable/sources/IBM Plex Sans Var-Regular.ufo',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Sans-Variable/sources/IBM Plex Sans Var-Thin Condensed Italic.ufo',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Sans-Variable/sources/IBM Plex Sans Var-Thin Condensed.ufo',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Sans-Variable/sources/IBM Plex Sans Var-Thin Italic.ufo',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Sans-Variable/sources/IBM Plex Sans Var-Thin.ufo',
    ]

    for path in paths:
        path = pathlib.Path(path)
        numFonts, opener = getOpener(path)
        for i in range(numFonts(path)):
            proj.addFont(path, i)
    controller = FGMainWindowController(proj)
