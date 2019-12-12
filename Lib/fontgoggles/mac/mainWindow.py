import asyncio
import contextlib
import pathlib
import unicodedata
import time
import AppKit
import objc
from vanilla import *
from fontTools.misc.arrayTools import offsetRect, scaleRect
from fontgoggles.font import openFonts
from fontgoggles.mac.aligningScrollView import AligningScrollView
from fontgoggles.misc.decorators import asyncTask, asyncTaskAutoCancel, suppressAndLogException
from fontgoggles.misc.rectTree import RectTree


def ClassNameIncrementer(clsName, bases, dct):
    import objc
    orgName = clsName
    counter = 0
    while True:
        try:
            objc.lookUpClass(clsName)
        except objc.nosuchclass_error:
            break
        counter += 1
        clsName = orgName + str(counter)
    return type(clsName, bases, dct)


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


class FGGlyphLineView(AppKit.NSView, metaclass=ClassNameIncrementer):

    _glyphs = None
    _rectTree = None
    _selection = None

    def isOpaque(self):
        return True

    def setGlyphs_(self, glyphs):
        self._glyphs = glyphs
        x = y = 0
        rectIndexList = [(gi.bounds, index) for index, gi in enumerate(glyphs) if gi.bounds is not None]
        self._rectTree = RectTree.fromSeq(rectIndexList)
        self._selection = set()
        self.setNeedsDisplay_(True)

    @suppressAndLogException
    def mouseDown_(self, event):
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
            # and take the first hit, if any. Fall back to the first.
            for index in indices:
                gi = self._glyphs[index]
                posX, posY = gi.pos
                if gi.path.containsPoint_((x - posX, y - posY)):
                    break
            else:
                index = indices[0]

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
        return 0.7 * height / 1000

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


class FontGroup(Group):

    nsViewClass = FGFontGroupView

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


fontItemNameTemplate = "fontItem_{index}"

def buildFontGroup(fontPaths, width, itemHeight):
    grp = FontGroup((0, 0, width, 900))
    y = 0
    for index, fontPath in enumerate(fontPaths):
        fontItemName = fontItemNameTemplate.format(index=index)
        fontItem = FontItem((0, y, 0, itemHeight), fontPath)
        setattr(grp, fontItemName, fontItem)
        y += itemHeight
    grp.setPosSize((0, 0, width, y))
    return grp


class FontItem(Group):

    def __init__(self, posSize, fontPath):
        super().__init__(posSize)
        self.glyphLine = GlyphLine((0, 0, 0, 0))
        self.filePath = TextBox((10, 0, 0, 17), f"{fontPath}", sizeStyle="regular")
        self.font = None

    def setText(self, txt):
        # TODO: FontItem should _not_ be responsible for shaping/setting, but
        # should simply receive a line of glyphs.
        if self.font is None:
            return
        glyphs, (finalX, finalY) = getGlyphRun(self.font, txt)
        self.glyphLine._nsObject.setGlyphs_(glyphs)


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


_textAlignments = dict(
    left=AppKit.NSTextAlignmentLeft,
    center=AppKit.NSTextAlignmentCenter,
    right=AppKit.NSTextAlignmentRight,
)

_textLineBreakModes = dict(
    wordwrap=AppKit.NSLineBreakByWordWrapping,
    charwrap=AppKit.NSLineBreakByCharWrapping,
    clipping=AppKit.NSLineBreakByClipping,
    trunchead=AppKit.NSLineBreakByTruncatingHead,
    trunctail=AppKit.NSLineBreakByTruncatingTail,
    truncmiddle=AppKit.NSLineBreakByTruncatingMiddle,
)

def textCell(align="left", lineBreakMode="wordwrap"):
    cell = AppKit.NSTextFieldCell.alloc().init()
    cell.setAlignment_(_textAlignments[align])
    cell.setLineBreakMode_(_textLineBreakModes[lineBreakMode])
    return cell


class FGMainController(AppKit.NSWindowController, metaclass=ClassNameIncrementer):

    def __new__(cls, fontPaths):
        return cls.alloc().init()

    def __init__(self, fontPaths):
        self.fontPaths = fontPaths
        self.itemHeight = 150

        initialText = "ABC abc 0123 :;?"

        sidebarWidth = 300
        unicodeListGroup = Group((0, 0, 0, 0))

        fontListGroup = Group((0, 0, 0, 0))
        sidebarGroup = Group((-sidebarWidth, 0, sidebarWidth, 0))

        columnDescriptions = [
            dict(title="index", width=34, cell=textCell("right")),
            dict(title="char", width=34, typingSensitive=True, cell=textCell("center")),
            dict(title="unicode", width=60, cell=textCell("right")),
            dict(title="unicode name", key="unicodeName", cell=textCell("left", "truncmiddle")),
        ]
        self.unicodeList = List((0, 0, 0, 0), [],
                columnDescriptions=columnDescriptions,
                allowsSorting=False, drawFocusRing=False, rowHeight=20)
        unicodeListGroup.unicodeList = self.unicodeList

        self._textEntry = EditText((10, 10, -10, 25), initialText, callback=self.textEntryCallback)
        fontListGroup.textEntry = self._textEntry

        paneDescriptors = [
            dict(view=unicodeListGroup, identifier="pane1", canCollapse=False,
                 size=300, resizeFlexibility=False),
            dict(view=fontListGroup, identifier="pane2", canCollapse=False),
        ]
        mainSplitView = SplitView((0, 0, -sidebarWidth, 0), paneDescriptors, dividerStyle=None)

        self._fontGroup = buildFontGroup(fontPaths, 3000, self.itemHeight)
        fontListGroup.fontList = AligningScrollView((0, 45, 0, 0), self._fontGroup, drawBackground=True, borderType=0)

        self.w = Window((800, 500), "FontGoggles", minSize=(200, 500), autosaveName="FontGogglesWindow")
        self.w.mainSplitView = mainSplitView
        self.w.sidebarGroup = sidebarGroup
        self.w.open()
        self.w._window.setWindowController_(self)
        self.w._window.makeFirstResponder_(fontListGroup.textEntry._nsObject)
        self.updateUnicodeList(self._textEntry.get())
        self.loadFonts()
        # self.testResizeFontItems()

    @asyncTask
    async def testResizeFontItems(self):
        await asyncio.sleep(2)
        itemSize = 150
        for i in range(50):
            itemSize *= 1.015
            itemSize = round(itemSize)
            self._fontGroup.resizeFontItems(itemSize)
            await asyncio.sleep(0.0)

    @objc.python_method
    async def _loadFont(self, fontPath, fontItem):
        async for font in openFonts(fontPath):
            # await asyncio.sleep(0)
            fontItem.font = font
            fontItem.setText(self._textEntry.get())
            break  # XXX

    def loadFonts(self):
        for fontPath, fontItem in zip(self.fontPaths, self.iterFontItems()):
            coro = self._loadFont(fontPath, fontItem)
            asyncio.create_task(coro)

    def iterFontItems(self):
        return self._fontGroup.iterFontItems()

    @asyncTaskAutoCancel
    async def textEntryCallback(self, sender):
        txt = sender.get()
        t = time.time()
        for fontItem in self.iterFontItems():
            fontItem.setText(txt)
            elapsed = time.time() - t
            if elapsed > 0.01:
                # time to unblock the event loop
                await asyncio.sleep(0)
                t = time.time()
        self.updateUnicodeList(txt, delay=0.05)

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

if __name__ == "__main__":
    fonts = [
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Italic.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Bold.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-ExtraLight.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Light.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Medium.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Regular.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-SemiBold.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Text.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Thin.ttf',
    ]
    fonts = [pathlib.Path(p) for p in fonts]
    x = FGMainController(fonts)
