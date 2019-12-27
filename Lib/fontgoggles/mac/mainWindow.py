import asyncio
import contextlib
import unicodedata
import time
import AppKit
import objc
from vanilla import *
from fontTools.misc.arrayTools import offsetRect
from fontgoggles.font import mergeAxes, mergeScriptsAndLanguages
from fontgoggles.mac.aligningScrollView import AligningScrollView
from fontgoggles.mac.drawing import *
from fontgoggles.mac.featureTagGroup import FeatureTagGroup
from fontgoggles.mac.fontList import FontList
from fontgoggles.mac.misc import ClassNameIncrementer, makeTextCell
from fontgoggles.mac.sliderGroup import SliderGroup
from fontgoggles.misc.decorators import asyncTaskAutoCancel, suppressAndLogException
from fontgoggles.misc.textInfo import TextInfo
from fontgoggles.misc import opentypeTags


# When the size of the line view needs to grow, overallocate this amount,
# to avoid having to resize the font line group too often. In other words,
# this value specifies some wiggle room: the font list can be a little
# larger than strictly necessary for fitting all glyphs.
fontListSizePadding = 120

# Width of the sidebar with direction/alignment/script/language/features controls etc.
sidebarWidth = 300


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

alignmentOptionsHorizontal = [
    "Automatic",
    "Left",
    "Right",
    "Center",
]

alignmentOptionsVertical = [
    "Automatic",
    "Top",
    "Bottom",
    "Center",
]


class FGMainWindowController(AppKit.NSWindowController, metaclass=ClassNameIncrementer):

    def __new__(cls, project):
        return cls.alloc().init()

    def __init__(self, project):
        self.project = project
        self.fontKeys = list(self.project.iterFontKeys())
        self.loadingFonts = set()
        self.allFeatureTagsGSUB = set()
        self.allFeatureTagsGPOS = set()
        self.allScriptsAndLanguages = {}
        self.allAxes = {}
        self.defaultFontItemSize = 150
        self.alignmentOverride = None
        self.featureState = {}
        self.varLocation = {}
        self._settingGlyphListPogrammatically = False

        unicodeListGroup = self.setupUnicodeListGroup()
        glyphListGroup = self.setupGlyphListGroup()
        fontListGroup = self.setupFontListGroup()
        sidebarGroup = self.setupSidebarGroup()

        paneDescriptors = [
            dict(view=glyphListGroup, identifier="glyphList", canCollapse=True,
                 size=220, resizeFlexibility=False),
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

        self.w = Window((800, 500), "FontGoggles", minSize=(800, 500), autosaveName="FontGogglesWindow",
                        fullScreenMode="primary")
        self.w.mainSplitView = mainSplitView
        self.w.open()
        self.w._window.setWindowController_(self)
        self.w._window.makeFirstResponder_(fontListGroup.textEntry._nsObject)
        self.setWindow_(self.w._window)

        initialText = "ABC abc 0123 :;?"
        self._textEntry.set(initialText)
        self.textEntryChangedCallback(self._textEntry)
        self.loadFonts()

    def windowTitleForDocumentDisplayName_(self, displayName):
        return f"FontGoggles — {displayName}"

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
            # "adv" is "ax" or "ay", depending on whether we are in vertical layout mode or not:
            dict(title="adv", key="adv", width=45, cell=makeTextCell("right")),
            dict(title="∆X", key="dx", width=45, cell=makeTextCell("right")),
            dict(title="∆Y", key="dy", width=45, cell=makeTextCell("right")),
            dict(title="cluster", width=40, cell=makeTextCell("right")),
            dict(title="gid", width=40, cell=makeTextCell("right")),
            # dummy filler column so "glyph" doesn't get to wide:
            dict(title="", key="_dummy_", minWidth=0, maxWidth=1400),
        ]
        self.glyphList = List((0, 40, 0, 0), [],
                              columnDescriptions=columnDescriptions,
                              allowsSorting=False, drawFocusRing=False,
                              rowHeight=20,
                              selectionCallback=self.glyphListSelectionChangedCallback)
        group.glyphList = self.glyphList
        return group

    @objc.python_method
    def setupFontListGroup(self):
        group = Group((0, 0, 0, 0))
        self._textEntry = EditText((10, 8, -10, 25), "", callback=self.textEntryChangedCallback)
        self._fontList = FontList(self.fontKeys, 300, self.defaultFontItemSize,
                                  selectionChangedCallback=self.fontListSelectionChangedCallback,
                                  glyphSelectionChangedCallback=self.fontListGlyphSelectionChangedCallback)
        self._fontListScrollView = AligningScrollView((0, 40, 0, 0), self._fontList, drawBackground=True,
                                                      minMagnification=0.2)
        group.fontList = self._fontListScrollView
        group.textEntry = self._textEntry
        return group

    @objc.python_method
    def setupSidebarGroup(self):
        group = Group((0, 0, 0, 0))
        group.generalSettings = self.setupGeneralSettingsGroup()
        x, y, w, h = group.generalSettings.getPosSize()
        group.feaVarTabs = Tabs((0, h + 6, 0, 0), ["Features", "Variations", "Options"])

        featuresTab = group.feaVarTabs[0]
        self.featuresGroup = FeatureTagGroup(sidebarWidth - 6, {}, callback=self.featuresChanged)
        featuresTab.main = AligningScrollView((0, 0, 0, 0), self.featuresGroup, drawBackground=False,
                                              hasHorizontalScroller=False,
                                              borderType=AppKit.NSNoBorder)

        variationsTab = group.feaVarTabs[1]
        self.variationsGroup = SliderGroup(sidebarWidth - 6, {}, callback=self.varLocationChanged)
        variationsTab.main = AligningScrollView((0, 0, 0, 0), self.variationsGroup, drawBackground=False,
                                              hasHorizontalScroller=False,
                                              borderType=AppKit.NSNoBorder)

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

        self.alignmentPopup = LabeledView(
            (10, y, -10, 40), "Visual alignment:",
            PopUpButton, alignmentOptionsHorizontal,
            callback=self.alignmentChangedCallback,
        )
        group.alignmentPopup = self.alignmentPopup
        y += 50

        self.scriptsPopup = LabeledView(
            (10, y, -10, 40), "Script:",
            PopUpButton, ['Automatic'],
            callback=self.scriptsPopupCallback,
        )
        group.scriptsPopup = self.scriptsPopup
        y += 50

        self.languagesPopup = LabeledView(
            (10, y, -10, 40), "Language:",
            PopUpButton, [],
            callback=self.languagesPopupCallback,
        )
        group.languagesPopup = self.languagesPopup
        y += 50

        group.setPosSize((0, 0, 0, y))
        return group

    def loadFonts(self):
        sharableFontData = {}
        firstKey = self.fontKeys[0] if self.fontKeys else None
        for fontKey, fontItem in zip(self.fontKeys, self.iterFontItems()):
            self.loadingFonts.add(fontKey)
            coro = self._loadFont(fontKey, fontItem, sharableFontData=sharableFontData)
            asyncio.create_task(coro)

    @objc.python_method
    async def _loadFont(self, fontKey, fontItem, sharableFontData):
        fontItem.setIsLoading(True)
        fontPath, fontNumber = fontKey
        await self.project.loadFont(fontPath, fontNumber, sharableFontData=sharableFontData)
        font = self.project.getFont(fontPath, fontNumber)
        await asyncio.sleep(0)
        fontItem.setIsLoading(False)
        self.allFeatureTagsGSUB.update(font.featuresGSUB)
        self.allFeatureTagsGPOS.update(font.featuresGPOS)
        self.allScriptsAndLanguages = mergeScriptsAndLanguages(self.allScriptsAndLanguages, font.scripts)
        self.allAxes = mergeAxes(self.allAxes, font.axes)
        self.setFontItemText(fontKey, fontItem)
        self.loadingFonts.remove(fontKey)
        if not self.loadingFonts:
            # All fonts have been loaded
            self.updateSidebarItems()
            self.fontListSelectionChangedCallback(self._fontList)

    def updateSidebarItems(self):
        self.featuresGroup.setTags({"GSUB": self.allFeatureTagsGSUB, "GPOS": self.allFeatureTagsGPOS})
        sliderInfo = {}
        for tag, axis in self.allAxes.items():
            defaultValue = axis["defaultValue"]
            if len(defaultValue) == 1:
                defaultValue = next(iter(defaultValue))
            else:
                defaultValue = None  # mixed default values
            sliderInfo[tag] = (f"{axis['name']} ({tag})", axis["minValue"], defaultValue, axis["maxValue"])
        self.variationsGroup.setSliderInfo(sliderInfo)
        scriptTags = sorted(self.allScriptsAndLanguages)
        scriptMenuTitles = ['Automatic'] + [f"{tag} – {opentypeTags.scripts.get(tag, '?')}" for tag in scriptTags]
        self.scriptsPopup.setItems(scriptMenuTitles)

    def iterFontItems(self):
        return self._fontList.iterFontItems()

    @objc.python_method
    def unicodeShowBiDiCheckBoxCallback(self, sender):
        self.updateUnicodeList()

    @objc.python_method
    def directionPopUpCallback(self, sender):
        popupValue = sender.get()
        self.unicodeShowBiDiCheckBox.enable(popupValue == 0)
        vertical = int(directionSettings[popupValue] in {"TTB", "BTT"})
        self.alignmentPopup.setItems([alignmentOptionsHorizontal, alignmentOptionsVertical][vertical])
        self._fontList.vertical = vertical
        self.textEntryChangedCallback(self._textEntry)

    @asyncTaskAutoCancel
    async def textEntryChangedCallback(self, sender):
        self.textInfo = TextInfo(sender.get())
        self.textInfo.shouldApplyBiDi = self.directionPopUp.get() == 0
        self.textInfo.directionOverride = directionSettings[self.directionPopUp.get()]
        self.textInfo.scriptOverride = self.scriptOverride
        self.textInfo.languageOverride = self.languageOverride
        if self.alignmentOverride is not None:
            align = self.alignmentOverride
        else:
            align = self.textInfo.suggestedAlignment

        if align != self._fontList.align:
            self.alignmentChangedCallback(self.alignmentPopup)
        else:
            self.updateTextEntryAlignment(align)

        self.updateUnicodeList(delay=0.05)
        t = time.time()
        firstKey = self.fontKeys[0] if self.fontKeys else None
        for fontKey, fontItem in zip(self.fontKeys, self.iterFontItems()):
            self.setFontItemText(fontKey, fontItem)
            elapsed = time.time() - t
            if elapsed > 0.01:
                # time to unblock the event loop
                await asyncio.sleep(0)
                t = time.time()
        newExtent = 300  # some minimum so that our filename label stays large enough
        for fontItem in self.iterFontItems():
            newExtent = max(newExtent, fontItem.minimumExtent)
        if not self._fontList.vertical:
            if self._fontList.width > newExtent + fontListSizePadding:
                # Shrink the font list
                self._fontList.width = newExtent
        else:
            if self._fontList.height > newExtent + fontListSizePadding:
                # Shrink the font list
                self._fontList.height = newExtent
        self.fontListSelectionChangedCallback(self._fontList)

    @objc.python_method
    def setFontItemText(self, fontKey, fontItem):
        fontPath, fontNumber = fontKey
        font = self.project.getFont(fontPath, fontNumber, None)
        if font is None:
            return
        glyphs, endPos = font.getGlyphRunFromTextInfo(self.textInfo, features=self.featureState,
                                                      varLocation=self.varLocation)
        addBoundingBoxes(glyphs)
        fontItem.setGlyphs(glyphs, endPos, font.unitsPerEm)
        minimumExtent = fontItem.minimumExtent
        if not self._fontList.vertical:
            if minimumExtent > self._fontList.width:
                # We make it a little wider than needed, so as to minimize the
                # number of times we need to make it grow, as it requires a full
                # redraw.
                self._fontList.width = minimumExtent + fontListSizePadding
        else:
            if minimumExtent > self._fontList.height:
                # We see above
                self._fontList.height = minimumExtent + fontListSizePadding

    @asyncTaskAutoCancel
    async def updateGlyphList(self, glyphs, selection=(), delay=0):
        if delay:
            # add a slight delay, so we won't do a lot of work when there's fast typing
            await asyncio.sleep(delay)
        if not self._fontList.vertical:
            keyMap = {"ax": "adv"}
        else:
            keyMap = {"ay": "adv"}
        glyphListData = [{keyMap.get(k, k): v for k, v in g.__dict__.items()} for g in glyphs]
        with self._changingGlyphList():
            self.glyphList.set(glyphListData)
            self.glyphList.setSelection(selection)

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

    @objc.python_method
    def fontListSelectionChangedCallback(self, sender):
        fontItem = sender.getSingleSelectedItem()
        if fontItem is not None:
            glyphs = fontItem.glyphs
            selection = fontItem.selection
        else:
            glyphs = []
            selection = []
        self.updateGlyphList(glyphs, selection, delay=0.05)

    @objc.python_method
    def fontListGlyphSelectionChangedCallback(self, sender):
        fontItem = sender.getSingleSelectedItem()
        if fontItem is not None:
            with self._changingGlyphList():
                self.glyphList.setSelection(fontItem.selection)

    @contextlib.contextmanager
    def _changingGlyphList(self):
        self._settingGlyphListPogrammatically = True
        yield
        self._settingGlyphListPogrammatically = False

    @objc.python_method
    def glyphListSelectionChangedCallback(self, sender):
        if self._settingGlyphListPogrammatically:
            return
        fontItem = self._fontList.getSingleSelectedItem()
        if fontItem is not None:
            fontItem.selection = set(self.glyphList.getSelection())

    @suppressAndLogException
    def alignmentChangedCallback(self, sender):
        values = [[None, "left", "right", "center"],
                  [None, "top", "bottom", "center"]][self._fontList.vertical]
        align = values[sender.get()]
        self.alignmentOverride = align
        if align is None:
            align = self.textInfo.suggestedAlignment
        self._fontList.align = align
        if not self._fontList.vertical:
            self._fontListScrollView.hAlign = align
            self._fontListScrollView.vAlign = "top"
        else:
            self._fontListScrollView.hAlign = "left"
            self._fontListScrollView.vAlign = align
        self.updateTextEntryAlignment(align)

    @property
    def scriptOverride(self):
        tag = _tagFromMenuItem(self.scriptsPopup.getItem())
        return None if tag == "Automatic" else tag

    @property
    def languageOverride(self):
        tag = _tagFromMenuItem(self.languagesPopup.getItem())
        return None if tag == "dflt" else tag

    @objc.python_method
    def scriptsPopupCallback(self, sender):
        tag = _tagFromMenuItem(sender.getItem())
        if tag == "Automatic":
            languages = []
        else:
            languages = [f"{tag} – {opentypeTags.languages.get(tag, ['?'])[0]}"
                         for tag in sorted(self.allScriptsAndLanguages[tag])]
        self.languagesPopup.setItems(['dflt – Default'] + languages)
        self.languagesPopup.set(0)
        self.textEntryChangedCallback(self._textEntry)

    @objc.python_method
    def languagesPopupCallback(self, sender):
        self.textEntryChangedCallback(self._textEntry)

    @objc.python_method
    def featuresChanged(self, sender):
        featureState = self.featuresGroup.get()
        featureState = {k: v for k, v in featureState.items() if v is not None}
        self.featureState = featureState
        self.textEntryChangedCallback(self._textEntry)

    @objc.python_method
    def varLocationChanged(self, sender):
        self.varLocation = {k: v for k, v in sender.get().items() if v is not None}
        self.textEntryChangedCallback(self._textEntry)

    @objc.python_method
    def updateTextEntryAlignment(self, align):
        if align == "right":
            nsAlign = AppKit.NSTextAlignmentRight
        elif align == "center":
            nsAlign = AppKit.NSTextAlignmentCenter
        else:
            nsAlign = AppKit.NSTextAlignmentLeft

        if self._textEntry._nsObject.alignment() == nsAlign:
            return

        fieldEditor = self.w._window.fieldEditor_forObject_(False, self._textEntry._nsObject)
        hasFocus = fieldEditor.delegate() is self._textEntry._nsObject
        if hasFocus:
            sel = fieldEditor.selectedRange()
            fieldEditor.setAlignment_(nsAlign)
            self._textEntry._nsObject.setAlignment_(nsAlign)
            # Now we've lost focus, let's get it again
            self.w._window.makeFirstResponder_(self._textEntry._nsObject)
            # Now we've lost the selection, let's restore it
            fieldEditor.setSelectedRange_(sel)
        else:
            self._textEntry._nsObject.setAlignment_(nsAlign)

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
        itemSize = min(1000, round(self._fontList.itemSize * (2 ** (1 / 3))))
        self._fontList.resizeFontItems(itemSize)

    def zoomOut_(self, sender):
        itemSize = max(50, round(self._fontList.itemSize / (2 ** (1 / 3))))
        self._fontList.resizeFontItems(itemSize)


class LabeledView(Group):

    def __init__(self, posSize, label, viewClass, *args, **kwargs):
        super().__init__(posSize)
        x, y, w, h = posSize
        assert h > 0
        self.label = TextBox((0, 0, 0, 0), label)
        self.view = viewClass((0, 20, 0, 20), *args, **kwargs)

    def get(self):
        return self.view.get()

    def set(self, value):
        self.view.set(value)

    def getItem(self):
        return self.view.getItem()

    def getItems(self):
        return self.view.getItems()

    def setItems(self, items):
        self.view.setItems(items)


def addBoundingBoxes(glyphs):
    for gi in glyphs:
        if gi.path.elementCount():
            gi.bounds = offsetRect(rectFromNSRect(gi.path.controlPointBounds()), *gi.pos)
        else:
            gi.bounds = None


def _tagFromMenuItem(title):
    if not title:
        return None
    tag = title.split()[0]
    if len(tag) < 4:
        tag += " " * (4 - len(tag))
    return tag
