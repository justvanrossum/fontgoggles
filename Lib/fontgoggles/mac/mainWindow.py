import asyncio
import pathlib
import unicodedata
import AppKit
import objc
from vanilla import *
from fontgoggles.font import openFonts
from fontgoggles.mac.aligningScrollView import AligningScrollView
from fontgoggles.misc.decorators import asyncTask, asyncTaskAutoCancel, suppressAndLogException


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



# -------------------

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

# -------------------

class FGGlyphLineView(AppKit.NSView, metaclass=ClassNameIncrementer):

    _glyphs = None

    def isOpaque(self):
        return True

    @suppressAndLogException
    def drawRect_(self, rect):
        AppKit.NSColor.whiteColor().set()
        AppKit.NSRectFill(rect)

        if not self._glyphs:
            return

        height = self.frame().size.height

        AppKit.NSColor.blackColor().set()
        translate(10, 0)
        scale(0.7 * height / 1000)
        translate(0, 300)
        for gi, outline in self._glyphs:
            outline.fill()
            translate(gi.ax, gi.ay)



class GlyphLine(Group):
    nsViewClass = FGGlyphLineView


fontItemNameTemplate = "fontItem_{index}"

def fontGroup(fontPaths, width):
    grp = Group((0, 0, width, 900))
    itemHeight = 150
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
        self.glyphLineTest = GlyphLine((0, 0, 0, 0))
        self.filePath = TextBox((10, 0, 0, 17), f"{fontPath}", sizeStyle="regular")
        self.font = None

    @asyncTaskAutoCancel
    async def setText(self, txt):
        if self.font is None:
            return
        glyphs = self.font.getGlyphRun(txt)
        glyphs = list(glyphs)
        self.glyphLineTest._nsObject._glyphs = glyphs
        self.glyphLineTest._nsObject.setNeedsDisplay_(True)


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

class FontGogglesMainController:

    def __init__(self, fontPaths):
        self.fontPaths = fontPaths

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
        self._fontGroup = fontGroup(fontPaths, 3000)
        fontListGroup.fontList = AligningScrollView((0, 45, 0, 0), self._fontGroup, drawBackground=False, borderType=0)

        paneDescriptors = [
            dict(view=unicodeListGroup, identifier="pane1", canCollapse=False,
                 size=300, resizeFlexibility=False),
            dict(view=fontListGroup, identifier="pane2", canCollapse=False),
        ]
        mainSplitView = SplitView((0, 0, -sidebarWidth, 0), paneDescriptors, dividerStyle=None)

        self.w = Window((800, 500), "FontGoggles", minSize=(200, 500), autosaveName="FontGogglesWindow")
        self.w.mainSplitView = mainSplitView
        self.w.sidebarGroup = sidebarGroup
        self.w.open()
        self.w._window.makeFirstResponder_(fontListGroup.textEntry._nsObject)
        self.updateUnicodeList(self._textEntry.get())
        self.loadFonts()

    @asyncTask
    async def loadFonts(self):
        for fontPath, fontItem in zip(self.fontPaths, self.iterFontItems()):
            async for font in openFonts(fontPath):
                await asyncio.sleep(0)
                fontItem.font = font
                fontItem.setText(str(self._textEntry.get()))

    def iterFontItems(self):
        for index in range(len(self.fontPaths)):
            fontItemName = fontItemNameTemplate.format(index=index)
            yield getattr(self._fontGroup, fontItemName)

    def textEntryCallback(self, sender):
        txt = sender.get()
        for fontItem in self.iterFontItems():
            fontItem.setText(txt)
        self.updateUnicodeList(txt)

    @asyncTaskAutoCancel
    async def updateUnicodeList(self, txt):
        # add a slight delay, so we won't do a lot of work when there's fast typing
        await asyncio.sleep(0.1)
        uniListData = []
        for index, char in enumerate(txt):
            uniListData.append(
                dict(index=index, char=char, unicode=f"U+{ord(char):04X}",
                     unicodeName=unicodedata.name(char, "?"))
            )
        self.unicodeList.set(uniListData)


if __name__ == "__main__":
    fonts = [
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Bold.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-ExtraLight.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Light.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Medium.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Regular.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-SemiBold.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Text.ttf',
        '/Users/just/code/git/ibm_plex/IBM-Plex-Serif/fonts/complete/ttf/IBMPlexSerif-Thin.ttf']
    fonts = [pathlib.Path(p) for p in fonts]
    FontGogglesMainController(fonts)
