import asyncio
import pathlib
import unicodedata
from vanilla import *
from fontgoggles.mac.aligningScrollView import AligningScrollView
from fontgoggles.misc.decorators import asyncTask


fontItemNameTemplate = "fontItem_{index}"

def fontGroup(fontPaths, width):
    grp = Group((0, 0, width, 900))
    itemHeight = 100
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
        self.filePath = TextBox((10, 0, 0, 17), f"{fontPath}", sizeStyle="regular")
        self.dummyTest = TextBox((10, 17, 0, 0))
        self._setTextTask = None

    def setText(self, txt):
        if self._setTextTask is not None and not self._setTextTask.done():
            self._setTextTask.cancel()
        self._setTextTask = self.simulateSlowness(txt)

    @asyncTask
    async def simulateSlowness(self, txt):
        await asyncio.sleep(0.25 * random())
        self.dummyTest.set(txt)


class FontGogglesMainController:

    def __init__(self, fontPaths):
        self.fontPaths = fontPaths

        sidebarWidth = 300
        unicodeListGroup = Group((0, 0, 0, 0))

        fontListGroup = Group((0, 0, 0, 0))
        sidebarGroup = Group((-sidebarWidth, 0, sidebarWidth, 0))

        columnDescriptions = [
            dict(title="index", width=34),
            dict(title="char", width=34, typingSensitive=True),
            dict(title="unicode", width=60),
            dict(title="unicode name", key="unicodeName"),
        ]
        self.unicodeList = List((0, 0, 0, 0), [],
                columnDescriptions=columnDescriptions,
                allowsSorting=False, drawFocusRing=False, rowHeight=20)
        unicodeListGroup.unicodeList = self.unicodeList

        fontListGroup.textEntry = EditText((10, 10, -10, 25), callback=self.textEntryCallback)
        self._fontGroup = fontGroup(fontPaths, 1000)
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
        self.updateUnicodeListTask = None

    def iterFontItems(self):
        for index in range(len(self.fontPaths)):
            fontItemName = fontItemNameTemplate.format(index=index)
            yield getattr(self._fontGroup, fontItemName)

    def textEntryCallback(self, sender):
        txt = sender.get()
        for fontItem in self.iterFontItems():
            fontItem.setText(txt)
        if self.updateUnicodeListTask is not None and not self.updateUnicodeListTask.done():
            self.updateUnicodeListTask.cancel()
        self.updateUnicodeListTask = self.updateUnicodeList(txt)

    @asyncTask
    async def updateUnicodeList(self, txt):
        await asyncio.sleep(0.2)
        uniListData = []
        for index, char in enumerate(txt):
            uniListData.append(
                dict(index=index, char=char, unicode=f"U+{ord(char):04X}", unicodeName=unicodedata.name(char, "?"))
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
