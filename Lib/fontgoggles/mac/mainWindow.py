import asyncio
from collections import defaultdict
import contextlib
import io
import logging
import os
import pathlib
import time
import traceback
import unicodedata
import AppKit
import objc
from vanilla import (ActionButton, CheckBox, EditText, Group, List, PopUpButton, SplitView, Tabs,
                     TextBox, TextEditor, VanillaBaseControl, Window)
from fontTools.misc.arrayTools import offsetRect
from fontgoggles.font import mergeAxes, mergeScriptsAndLanguages
from fontgoggles.font.baseFont import GlyphsRun
from fontgoggles.mac.aligningScrollView import AligningScrollView
from fontgoggles.mac.drawing import rectFromNSRect
from fontgoggles.mac.featureTagGroup import FeatureTagGroup
from fontgoggles.mac.fileObserver import getFileObserver
from fontgoggles.mac.fontList import FontList, fontItemMinimumSize, fontItemMaximumSize, makeUndoProxy
from fontgoggles.mac.misc import ClassNameIncrementer, makeTextCell
from fontgoggles.mac.sliderGroup import SliderGroup, SliderPlus
from fontgoggles.compile.compilerPool import CompilerError
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
    (None, None),  # separator
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
        self.projectFontsProxy = makeUndoProxy(self.project.fonts, self._projectFontsChanged)
        self.observedPaths = {}
        self.defaultFontItemSize = 150
        self.alignmentOverride = None
        self.featureState = {}
        self.varLocation = {}
        self._callbackRecursionLock = 0
        self._previouslySingleSelectedItem = None

        unicodeListGroup = self.setupUnicodeListGroup()
        glyphListGroup = self.setupGlyphListGroup()
        fontListGroup = self.setupFontListGroup()
        sidebarGroup = self.setupSidebarGroup()

        paneDescriptors = [
            dict(view=glyphListGroup, identifier="glyphList", canCollapse=True,
                 size=230, minSize=80, resizeFlexibility=False),
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

        self.w = Window((800, 500), "FontGoggles", minSize=(900, 500), autosaveName="FontGogglesWindow",
                        fullScreenMode="primary")
        self.w.mainSplitView = mainSplitView
        self.w.open()
        self.w._window.setWindowController_(self)
        self.w._window.makeFirstResponder_(fontListGroup.textEntry._nsObject)
        self.setWindow_(self.w._window)

        initialText = "ABC abc 0123 :;?"
        self.textEntry.set(initialText)
        self.textEntryChangedCallback(self.textEntry)
        self.w.bind("close", self._windowCloseCallback)
        self.updateFileObservers()
        self.loadFonts()

    @suppressAndLogException
    def _windowCloseCallback(self, sender):
        obs = getFileObserver()
        for path in self.observedPaths:
            obs.removeObserver(path, self._fileChanged)
        self.__dict__.clear()

    def windowTitleForDocumentDisplayName_(self, displayName):
        return f"FontGoggles — {displayName}"

    @objc.python_method
    def setupUnicodeListGroup(self):
        group = Group((0, 0, 0, 0))
        columnDescriptions = [
            # dict(title="index", width=34, cell=makeTextCell("right")),
            dict(title="char", width=30, typingSensitive=True, cell=makeTextCell("center")),
            dict(title="unicode", width=60, cell=makeTextCell("right")),
            dict(title="unicode name", width=200, minWidth=200, maxWidth=400, key="unicodeName",
                 cell=makeTextCell("left", "truncmiddle")),
        ]
        self.unicodeList = List((0, 40, 0, 0), [],
                                columnDescriptions=columnDescriptions,
                                allowsSorting=False, drawFocusRing=False, rowHeight=20,
                                selectionCallback=self.unicodeListSelectionChangedCallback)
        self.unicodeShowBiDiCheckBox = CheckBox((10, 8, -10, 20), "BiDi",
                                                callback=self.unicodeShowBiDiCheckBoxCallback)
        self.unicodeShowBiDiCheckBox._nsObject.setToolTip_(
            "If this option is on, you see the result of Bi-Directional processing "
            "in the list below, instead of the original text. It does not affect "
            "the rendered text.")
        group.unicodeShowBiDiCheckBox = self.unicodeShowBiDiCheckBox
        group.unicodeList = self.unicodeList
        return group

    @objc.python_method
    def setupGlyphListGroup(self):
        group = Group((0, 0, 0, 0))
        columnDescriptions = [
            # dict(title="index", width=34, cell=makeTextCell("right")),
            dict(title="glyph", key="name", width=80, minWidth=80, maxWidth=200,
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
        textRightMargin = 70
        self.textEntry = EditText((10, 8, -textRightMargin, 25), "", callback=self.textEntryChangedCallback)
        self.textFileStepper = Stepper((-textRightMargin + 5, 8, 12, 25), 0, 0, 0)
        items = [
            dict(title="Load text file..."),
            dict(title="Save"),
            dict(title="Save as..."),
            dict(title="Revert"),
        ]
        self.textFileMenuButton = ActionButton((-textRightMargin + 25, 8, -10, 25), items)

        self.fontList = FontList(self.project, self.projectFontsProxy, 300, self.defaultFontItemSize,
                                 selectionChangedCallback=self.fontListSelectionChangedCallback,
                                 glyphSelectionChangedCallback=self.fontListGlyphSelectionChangedCallback,
                                 arrowKeyCallback=self.fontListArrowKeyCallback)
        self._fontListScrollView = AligningScrollView((0, 0, 0, 0), self.fontList, drawBackground=True,
                                                      minMagnification=0.4, maxMagnification=15,
                                                      forwardDragAndDrop=True)

        self.compileOutput = OutputText((0, 0, 0, 0))

        paneDescriptors = [
            dict(view=self._fontListScrollView, identifier="fontList", canCollapse=False,
                 size=230, minSize=150),
            dict(view=self.compileOutput, identifier="compileOutput", canCollapse=True,
                 size=80, minSize=30, resizeFlexibility=False),
        ]
        self.fontListSplitView = SplitView((0, 40, 0, 0), paneDescriptors, dividerStyle="thin",
                                           isVertical=False)
        # self.fontListSplitView.togglePane("compileOutput")

        group.textEntry = self.textEntry
        group.textFileStepper = self.textFileStepper
        group.textFileMenuButton = self.textFileMenuButton
        group.fontListSplitView = self.fontListSplitView
        self.fontList._nsObject.subscribeToMagnification_(self._fontListScrollView._nsObject)
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

        optionsTab = group.feaVarTabs[2]
        # TODO initial value from where?
        y = 10
        optionsTab.relativeSizeSlider = SliderPlus((10, y, sidebarWidth - 26, 40), "Size", 25, 70, 125,
                                                   callback=self.relativeSizeChangedCallback)
        y += 50
        optionsTab.relativeBaselineSlider = SliderPlus((10, y, sidebarWidth - 26, 40), "Baseline", 0, 25, 100,
                                                       callback=self.relativeBaselineChangedCallback)
        y += 50
        optionsTab.relativeMarginSlider = SliderPlus((10, y, sidebarWidth - 26, 40), "Margin", 0, 10, 100,
                                                     callback=self.relativeMarginChangedCallback)
        y += 50

        return group

    def setupGeneralSettingsGroup(self):
        group = Group((0, 0, 0, 0))
        y = 10

        directions = [label if label is not None else AppKit.NSMenuItem.separatorItem() for label in directionOptions]

        self.directionPopUp = LabeledView(
            (10, y, -10, 40), "Direction/orientation:",
            PopUpButton, directions,
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
        self.scriptsPopupCallback(self.scriptsPopup)
        return group

    def updateFileObservers(self):
        obs = getFileObserver()
        newObservedPaths = defaultdict(list)
        for fontItemInfo in self.project.fonts:
            newObservedPaths[fontItemInfo.fontKey[0]].append(fontItemInfo)
            if fontItemInfo.font is not None:
                for path in fontItemInfo.font.getExternalFiles():
                    assert isinstance(path, os.PathLike)
                    newObservedPaths[path].append(fontItemInfo)
        newPaths = set(newObservedPaths)
        oldPaths = set(self.observedPaths)
        for path in newPaths - oldPaths:
            obs.addObserver(path, self._fileChanged)
        for path in oldPaths - newPaths:
            obs.removeObserver(path, self._fileChanged)
        self.observedPaths = newObservedPaths

    @objc.python_method
    def addExternalFileObservers(self, externalFiles, fontItemInfo):
        obs = getFileObserver()
        for path in externalFiles:
            assert isinstance(path, os.PathLike), "Path object expected"
            if fontItemInfo not in self.observedPaths[path]:
                self.observedPaths[path].append(fontItemInfo)
                obs.addObserver(path, self._fileChanged)

    @suppressAndLogException
    def _fileChanged(self, oldPath, newPath, wasModified):
        oldPath = pathlib.Path(oldPath)
        if newPath is not None:
            newPath = pathlib.Path(newPath)
        if oldPath == newPath:
            logging.info("file changed event: %s wasModified=%s", oldPath, wasModified)
        else:
            logging.info("file changed event: %s -> %s wasModified=%s", oldPath, newPath, wasModified)
        didMove = False
        for fontItemInfo in self.observedPaths[oldPath]:
            if oldPath == fontItemInfo.fontPath:
                externalFile = None
                if oldPath != newPath and newPath is not None:
                    didMove = True
                    fontItemInfo.fontPath = newPath
                    fontItem = self.fontList.getFontItem(fontItemInfo.identifier)
                    fontItem.setFontKey(fontItemInfo.fontKey)
            else:
                externalFile = oldPath
            if wasModified:
                font = fontItemInfo.font
                if font is not None:
                    if font.canReloadWithChange(externalFile):
                        # The font will be reloaded in-place
                        fontItemInfo.wantsReload = True
                    else:
                        # The font will be reloaded from scratch
                        fontItemInfo.unload()

        if didMove:
            self.updateFileObservers()
        if wasModified:
            self.loadFonts()

    @suppressAndLogException
    def _projectFontsChanged(self, changeSet):
        if any(change.op == "remove" for change in changeSet):
            self.fontList.purgeFontItems()
            self.project.purgeFonts()
        fontItemsNeedingTextUpdate = self.fontList.refitFontItems()
        # TODO: Consider keeping selection, which can only work if we store
        # the selection as a set of identifiers instead of indices, because
        # once we get here the indices are no longer valid, hence the need
        # to completely reset the selection.
        self.fontList.resetSelection()
        # TODO: rethink factorization of the next bit.
        # - refitFontItems() added new items
        # - the font for the new item may or may not be loaded
        # - if not loaded, loadFonts() will load it and will also set the text
        # - if loaded, the text needs to be set separately
        for fontItemInfo, fontItem in fontItemsNeedingTextUpdate:
            self.setFontItemText(fontItemInfo, fontItem)
        self.updateFileObservers()
        self.loadFonts()

    @asyncTaskAutoCancel
    async def loadFonts(self):
        """This loads fonts that aren't yet loaded, and updates all information
        regarding features, scripts/languages and variations.
        """
        coros = []
        for fontItemInfo, fontItem in self.iterFontItemInfoAndItems():
            if fontItemInfo.font is None or fontItemInfo.wantsReload:
                coros.append(self._loadFont(fontItemInfo, fontItem))
        await asyncio.gather(*coros)
        self._updateSidebarItems(*self._gatherSidebarInfo(self.project.fonts))
        self.fontListSelectionChangedCallback(self.fontList)

    @objc.python_method
    async def _loadFont(self, fontItemInfo, fontItem):
        fontItem.setIsLoading(True)
        try:
            try:
                fontItem.clearCompileOutput()
                await fontItemInfo.load(outputWriter=fontItem.writeCompileOutput)
                externalFiles = fontItemInfo.font.getExternalFiles()
                if externalFiles:
                    self.addExternalFileObservers(externalFiles, fontItemInfo)
                await asyncio.sleep(0)
            finally:
                fontItem.setIsLoading(False)
        except CompilerError as e:
            fontItem.glyphs = GlyphsRun(0, 1000, False)
            fontItem.writeCompileOutput(f"{e!r}\n")
        except asyncio.CancelledError:
            raise
        except Exception:
            fontItem.glyphs = GlyphsRun(0, 1000, False)
            fontItem.writeCompileOutput(traceback.format_exc())
        else:
            self.setFontItemText(fontItemInfo, fontItem)
            self.growFontListFromItem(fontItem)

    @staticmethod
    def _gatherSidebarInfo(fonts):
        allFeatureTagsGSUB = set()
        allFeatureTagsGPOS = set()
        allAxes = []
        allScriptsAndLanguages = []
        for fontItemInfo in fonts:
            font = fontItemInfo.font
            if font is None:
                continue
            allFeatureTagsGSUB.update(font.featuresGSUB)
            allFeatureTagsGPOS.update(font.featuresGPOS)
            allAxes.append(font.axes)
            allScriptsAndLanguages.append(font.scripts)
        allAxes = mergeAxes(*allAxes)
        allScriptsAndLanguages = mergeScriptsAndLanguages(*allScriptsAndLanguages)
        return allFeatureTagsGSUB, allFeatureTagsGPOS, allAxes, allScriptsAndLanguages

    @objc.python_method
    def _updateSidebarItems(self, allFeatureTagsGSUB, allFeatureTagsGPOS, allAxes,
                            allScriptsAndLanguages):
        self.featuresGroup.setTags({"GSUB": allFeatureTagsGSUB, "GPOS": allFeatureTagsGPOS})
        sliderInfo = {}
        for tag, axis in allAxes.items():
            defaultValue = axis["defaultValue"]
            if len(defaultValue) == 1:
                defaultValue = next(iter(defaultValue))
            else:
                defaultValue = None  # mixed default values
            sliderInfo[tag] = (f"{axis['name']} ({tag})", axis["minValue"], defaultValue, axis["maxValue"])
        self.variationsGroup.setSliderInfo(sliderInfo)
        scriptTags = sorted(allScriptsAndLanguages)
        scriptMenuTitles = ['Automatic'] + [f"{tag} – {opentypeTags.scripts.get(tag, '?')}" for tag in scriptTags]
        selectedItem = self.scriptsPopup.getItem()
        if selectedItem in scriptMenuTitles:
            newSelectedIndex = scriptMenuTitles.index(selectedItem)
        else:
            newSelectedIndex = 0
        self.scriptsPopup.setItems(scriptMenuTitles)
        self.scriptsPopup.set(newSelectedIndex)
        self.allScriptsAndLanguages = allScriptsAndLanguages

    def iterFontItems(self):
        return self.fontList.iterFontItems()

    def iterFontItemInfoAndItems(self):
        return self.fontList.iterFontItemInfoAndItems()

    @objc.python_method
    def unicodeShowBiDiCheckBoxCallback(self, sender):
        self.updateUnicodeList()

    @asyncTaskAutoCancel
    async def textEntryChangedCallback(self, sender, updateUnicodeList=True):
        if not hasattr(self, "directionPopUp"):
            # Our window already closed, and our poor async task is too
            # late. Nothing left to do.
            return
        self.textInfo = TextInfo(sender.get())
        self.textInfo.shouldApplyBiDi = self.directionPopUp.get() == 0
        self.textInfo.directionOverride = directionSettings[self.directionPopUp.get()]
        self.textInfo.scriptOverride = self.scriptOverride
        self.textInfo.languageOverride = self.languageOverride
        if self.alignmentOverride is not None:
            align = self.alignmentOverride
        else:
            align = self.textInfo.suggestedAlignment

        if align != self.fontList.align:
            self.alignmentChangedCallback(self.alignmentPopup)
        else:
            self.updateTextEntryAlignment(align)

        if updateUnicodeList:
            # Immediately reset selection, so that delayed async clients
            # won't get a stale selection.
            self.unicodeList.setSelection([])
            self.updateUnicodeList(delay=0.05)
        else:
            charSelection = self.unicodeList.getSelection()
        t = time.time()
        for fontItemInfo, fontItem in self.iterFontItemInfoAndItems():
            self.setFontItemText(fontItemInfo, fontItem)
            elapsed = time.time() - t
            if elapsed > 0.01:
                # time to unblock the event loop
                await asyncio.sleep(0)
                t = time.time()
        self.growOrShrinkFontList()
        self.fontListSelectionChangedCallback(self.fontList)
        if not updateUnicodeList:
            self.unicodeList.setSelection(charSelection)
            self.unicodeListSelectionChangedCallback(self.unicodeList)

    @objc.python_method
    def setFontItemText(self, fontItemInfo, fontItem):
        font = fontItemInfo.font
        if font is None:
            return
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            glyphs = font.getGlyphRunFromTextInfo(self.textInfo, features=self.featureState,
                                                  varLocation=self.varLocation)
        stderr = stderr.getvalue()
        if stderr:
            fontItem.writeCompileOutput(stderr)

        addBoundingBoxes(glyphs)
        fontItem.glyphs = glyphs
        charSelection = self.unicodeList.getSelection()
        if charSelection:
            with self.blockCallbackRecursion():
                fontItem.selection = fontItem.glyphs.mapCharsToGlyphs(charSelection)

    def growOrShrinkFontList(self):
        newExtent = 300  # some minimum so that our filename label stays large enough
        for fontItem in self.iterFontItems():
            newExtent = max(newExtent, fontItem.minimumExtent)
        if not self.fontList.vertical:
            if self.fontList.width > newExtent + fontListSizePadding:
                self.fontList.width = newExtent
            elif self.fontList.width < newExtent:
                self.fontList.width = newExtent + fontListSizePadding
        else:
            if self.fontList.height > newExtent + fontListSizePadding:
                self.fontList.height = newExtent
            elif self.fontList.height < newExtent:
                self.fontList.height = newExtent + fontListSizePadding

    @objc.python_method
    def growFontListFromItem(self, fontItem):
        minimumExtent = fontItem.minimumExtent
        if not self.fontList.vertical:
            if minimumExtent > self.fontList.width:
                # We make it a little wider than needed, so as to minimize the
                # number of times we need to make it grow, as it requires a full
                # redraw.
                self.fontList.width = minimumExtent + fontListSizePadding
        else:
            if minimumExtent > self.fontList.height:
                # We see above
                self.fontList.height = minimumExtent + fontListSizePadding

    @contextlib.contextmanager
    def blockCallbackRecursion(self):
        self._callbackRecursionLock += 1
        yield
        self._callbackRecursionLock -= 1

    @asyncTaskAutoCancel
    async def updateGlyphList(self, glyphs, delay=0):
        if not hasattr(self, "fontList"):
            # Window closed before we got to run
            return
        if delay:
            # add a slight delay, so we won't do a lot of work when there's fast typing
            await asyncio.sleep(delay)
        if not self.fontList.vertical:
            keyMap = {"ax": "adv"}
        else:
            keyMap = {"ay": "adv"}
        if glyphs is None:
            glyphs = []
        glyphListData = [{keyMap.get(k, k): v for k, v in g.__dict__.items()} for g in glyphs]
        with self.blockCallbackRecursion():
            self.glyphList.set(glyphListData)
            fontItem = self.fontList.getSingleSelectedItem()
            if fontItem is not None:
                self.glyphList.setSelection(fontItem.selection)

    @asyncTaskAutoCancel
    async def updateUnicodeList(self, selection=None, delay=0):
        if not hasattr(self, "unicodeShowBiDiCheckBox"):
            # Window closed before we got to run
            return
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
        if selection is not None:
            self.unicodeList.setSelection(selection)

    @objc.python_method
    def fontListSelectionChangedCallback(self, sender):
        fontItem = sender.getSingleSelectedItem()
        if self._previouslySingleSelectedItem is not None:
            self._previouslySingleSelectedItem.setAuxillaryOutput(None)
        if fontItem is not None:
            glyphs = fontItem.glyphs
            self.updateUnicodeListSelection(fontItem)
            self.compileOutput.set(fontItem.getCompileOutput())
            fontItem.setAuxillaryOutput(self.compileOutput)
        else:
            glyphs = []
            self.compileOutput.set("")
        self._previouslySingleSelectedItem = fontItem
        self.updateGlyphList(glyphs, delay=0.05)

    @objc.python_method
    def fontListGlyphSelectionChangedCallback(self, sender):
        if self._callbackRecursionLock:
            return
        selectedFontItem = sender.getSingleSelectedItem()
        if selectedFontItem is None:
            self.unicodeList.setSelection([])
            return
        if selectedFontItem.glyphs is not None:
            charIndices = selectedFontItem.glyphs.mapGlyphsToChars(selectedFontItem.selection)
        else:
            charIndices = []

        with self.blockCallbackRecursion():
            for fontItem in self.iterFontItems():
                if fontItem is selectedFontItem:
                    self.glyphList.setSelection(fontItem.selection)
                    self.updateUnicodeListSelection(fontItem)
                elif fontItem.glyphs is not None:
                    fontItem.selection = fontItem.glyphs.mapCharsToGlyphs(charIndices)

    @objc.python_method
    def fontListArrowKeyCallback(self, sender, event):
        if not self.fontList.vertical:
            event = transposeArrowKeyEvent(event)
        if len(self.glyphList) > 0:
            self.glyphList._nsObject.documentView().keyDown_(event)
        elif len(self.unicodeList) > 0:
            if self.textInfo.text == self.textInfo.originalText:
                # Either automatic direction (by bidi algo + HB) or explicit
                # reversal of direction
                if (self.textInfo.directionForShaper is None and self.textInfo.baseDirection == "R") \
                        or self.textInfo.directionForShaper in ("RTL", "BTT"):
                    event = flipArrowKeyEvent(event)
                self.unicodeList._nsObject.documentView().keyDown_(event)
            elif self.unicodeShowBiDiCheckBox.get():
                # We're showing post-BiDi characters, which should lign up
                # with our glyphs
                self.unicodeList._nsObject.documentView().keyDown_(event)
            else:
                # BiDi processing is on, and we're looking at the original
                # text sequence (before BiDi processing). We convert our
                # selection to post-BiDi, base the new selection on that,
                # then convert back to pre-BiDi. This way we should key
                # through the glyphs by character, but in the order of the
                # glyphs.
                if event.characters() == AppKit.NSUpArrowFunctionKey:
                    direction = -1
                else:
                    direction = 1
                charSelection = self.unicodeList.getSelection()
                if not charSelection:
                    if direction == -1:
                        newCharselection = [len(self.unicodeList) - 1]
                    else:
                        newCharselection = [0]
                else:
                    charSelection = self.textInfo.mapToBiDi(charSelection)
                    if direction == -1:
                        newCharselection = [max(0, min(charSelection) - 1)]
                    else:
                        newCharselection = [min(len(self.unicodeList) - 1, max(charSelection) + 1)]
                newCharselection = self.textInfo.mapFromBiDi(newCharselection)
                if event.modifierFlags() & AppKit.NSEventModifierFlagShift:
                    newCharselection = set(newCharselection + self.unicodeList.getSelection())
                self.unicodeList.setSelection(newCharselection)
        self.fontList.scrollGlyphSelectionToVisible()

    @objc.python_method
    def glyphListSelectionChangedCallback(self, sender):
        if self._callbackRecursionLock:
            return
        selectedFontItem = self.fontList.getSingleSelectedItem()
        if selectedFontItem is None:
            return
        glyphIndices = self.glyphList.getSelection()
        if selectedFontItem.glyphs is not None:
            charIndices = selectedFontItem.glyphs.mapGlyphsToChars(glyphIndices)
        else:
            charIndices = []

        with self.blockCallbackRecursion():
            for fontItem in self.iterFontItems():
                if fontItem is selectedFontItem:
                    fontItem.selection = set(glyphIndices)
                    self.updateUnicodeListSelection(fontItem)
                elif fontItem.glyphs is not None:
                    fontItem.selection = fontItem.glyphs.mapCharsToGlyphs(charIndices)
        self.fontList.scrollGlyphSelectionToVisible()

    @objc.python_method
    def updateUnicodeListSelection(self, fontItem):
        if fontItem.glyphs is None:
            return
        charIndices = fontItem.glyphs.mapGlyphsToChars(fontItem.selection)

        if self.textInfo.shouldApplyBiDi and not self.unicodeShowBiDiCheckBox.get():
            charIndices = self.textInfo.mapFromBiDi(charIndices)

        with self.blockCallbackRecursion():
            self.unicodeList.setSelection(charIndices)

    @objc.python_method
    def unicodeListSelectionChangedCallback(self, sender):
        if self._callbackRecursionLock:
            return
        selectedFontItem = self.fontList.getSingleSelectedItem()

        charIndices = set(sender.getSelection())
        if self.textInfo.shouldApplyBiDi and not self.unicodeShowBiDiCheckBox.get():
            charIndices = self.textInfo.mapToBiDi(charIndices)

        with self.blockCallbackRecursion():
            for fontItem in self.iterFontItems():
                if fontItem.glyphs is None:
                    continue
                selectedGlyphs = fontItem.glyphs.mapCharsToGlyphs(charIndices)
                if fontItem is selectedFontItem:
                    self.glyphList.setSelection(selectedGlyphs)
                fontItem.selection = selectedGlyphs
        self.fontList.scrollGlyphSelectionToVisible()

    @objc.python_method
    def directionPopUpCallback(self, sender):
        popupValue = sender.get()
        self.unicodeShowBiDiCheckBox.enable(popupValue == 0)
        vertical = int(directionSettings[popupValue] in {"TTB", "BTT"})
        self.alignmentPopup.setItems([alignmentOptionsHorizontal, alignmentOptionsVertical][vertical])
        self.fontList.vertical = vertical
        self.alignmentChangedCallback(self.alignmentPopup)
        self.textEntryChangedCallback(self.textEntry)

    @suppressAndLogException
    def alignmentChangedCallback(self, sender):
        values = [[None, "left", "right", "center"],
                  [None, "top", "bottom", "center"]][self.fontList.vertical]
        align = values[sender.get()]
        self.alignmentOverride = align
        if align is None:
            align = self.textInfo.suggestedAlignment
        self.fontList.align = align
        if not self.fontList.vertical:
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
        languages = ['dflt – Default'] + languages
        selectedItem = self.languagesPopup.getItem()
        if selectedItem in languages:
            newSelectedIndex = languages.index(selectedItem)
        else:
            newSelectedIndex = 0
        self.languagesPopup.setItems(languages)
        self.languagesPopup.set(newSelectedIndex)
        self.textEntryChangedCallback(self.textEntry, updateUnicodeList=False)

    @objc.python_method
    def languagesPopupCallback(self, sender):
        self.textEntryChangedCallback(self.textEntry, updateUnicodeList=False)

    @objc.python_method
    def featuresChanged(self, sender):
        self.featureState = self.featuresGroup.get()
        self.textEntryChangedCallback(self.textEntry, updateUnicodeList=False)

    @objc.python_method
    def varLocationChanged(self, sender):
        self.varLocation = {k: v for k, v in sender.get().items() if v is not None}
        self.textEntryChangedCallback(self.textEntry, updateUnicodeList=False)

    @objc.python_method
    def relativeSizeChangedCallback(self, sender):
        if not hasattr(self, "fontList"):
            # Happens when the window is closing and the text field of the slider has focus
            return
        self.fontList.relativeFontSize = sender.get() / 100
        self.growOrShrinkFontList()

    @objc.python_method
    def relativeBaselineChangedCallback(self, sender):
        if not hasattr(self, "fontList"):
            # Happens when the window is closing and the text field of the slider has focus
            return
        value = sender.get() / 100
        if self.fontList.vertical:
            self.fontList.relativeVBaseline = value
        else:
            self.fontList.relativeHBaseline = value

    @objc.python_method
    def relativeMarginChangedCallback(self, sender):
        if not hasattr(self, "fontList"):
            # Happens when the window is closing and the text field of the slider has focus
            return
        self.fontList.relativeMargin = sender.get() / 100
        self.growOrShrinkFontList()

    @objc.python_method
    def updateTextEntryAlignment(self, align):
        if self.fontList.vertical:
            align = "left"
        if align == "right":
            nsAlign = AppKit.NSTextAlignmentRight
        elif align == "center":
            nsAlign = AppKit.NSTextAlignmentCenter
        else:
            nsAlign = AppKit.NSTextAlignmentLeft

        if self.textEntry._nsObject.alignment() == nsAlign:
            return

        fieldEditor = self.w._window.fieldEditor_forObject_(False, self.textEntry._nsObject)
        hasFocus = fieldEditor.delegate() is self.textEntry._nsObject
        if hasFocus:
            sel = fieldEditor.selectedRange()
            fieldEditor.setAlignment_(nsAlign)
            self.textEntry._nsObject.setAlignment_(nsAlign)
            # Now we've lost focus, let's get it again
            self.w._window.makeFirstResponder_(self.textEntry._nsObject)
            # Now we've lost the selection, let's restore it
            fieldEditor.setSelectedRange_(sel)
        else:
            self.textEntry._nsObject.setAlignment_(nsAlign)

    def showCharacterList_(self, sender):
        self.w.mainSplitView.togglePane("characterList")

    def showGlyphList_(self, sender):
        self.subSplitView.togglePane("glyphList")

    def showCompileOutput_(self, sender):
        self.fontListSplitView.togglePane("compileOutput")

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
        elif action == "showCompileOutput:":
            isVisible = not self.fontListSplitView.isPaneVisible("compileOutput")
        elif action == "showFormattingOptions:":
            isVisible = not self.w.mainSplitView.isPaneVisible("formattingOptions")
        if isVisible is not None:
            if isVisible:
                findReplace.reverse()
            newTitle = title.replace(findReplace[0], findReplace[1])
            sender.setTitle_(newTitle)
        return True

    def zoomIn_(self, sender):
        itemSize = min(fontItemMaximumSize, round(self.fontList.itemSize * (2 ** (1 / 3))))
        self.fontList.resizeFontItems(itemSize)

    def zoomOut_(self, sender):
        itemSize = max(fontItemMinimumSize, round(self.fontList.itemSize / (2 ** (1 / 3))))
        self.fontList.resizeFontItems(itemSize)


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

    def setItem(self, item):
        self.view.setItem(item)

    def getItems(self):
        return self.view.getItems()

    def setItems(self, items):
        self.view.setItems(items)


class OutputText(TextEditor):

    def __init__(self, posSize):
        super().__init__(posSize, readOnly=True)
        self.textAttributes = {
            AppKit.NSFontAttributeName: AppKit.NSFont.fontWithName_size_("Menlo", 12),
            AppKit.NSForegroundColorAttributeName: AppKit.NSColor.textColor(),
        }
        self._textView.setRichText_(False)
        # self.write("Testing a longer line of text, a blank line\n\nand something short.\n" * 20)

    def set(self, text):
        self.clear()
        self.write(text)
        self.scrollToEnd()

    def clear(self):
        st = self._textView.textStorage()
        st.deleteCharactersInRange_((0, st.length()))

    def write(self, text):
        attrString = AppKit.NSAttributedString.alloc().initWithString_attributes_(text, self.textAttributes)
        st = self._textView.textStorage()
        st.appendAttributedString_(attrString)
        # If we call scrollToEnd right away it seems to have no effect.
        # If we defer to the next opportunity in the event loop it works fine.
        loop = asyncio.get_running_loop()
        loop.call_soon(self.scrollToEnd)

    def scrollToEnd(self):
        st = self._textView.textStorage()
        self._textView.scrollRangeToVisible_((st.length(), 0))


class Stepper(VanillaBaseControl):

    nsStepperClass = AppKit.NSStepper

    def __init__(self, posSize, minValue=0, maxValue=10, increment=1, callback=None):
        self._setupView(self.nsStepperClass, posSize, callback=callback)
        self.minValue = minValue
        self.maxValue = maxValue
        self.increment = increment

    def get(self):
        return self._nsObject.intValue()

    def set(self, value):
        return self._nsObject.setIntValue_(value)

    @property
    def increment(self):
        return self._nsObject.increment()

    @increment.setter
    def increment(self, value):
        self._nsObject.setIncrement_(value)

    @property
    def minValue(self):
        return self._nsObject.minValue()

    @minValue.setter
    def minValue(self, value):
        self._nsObject.setMinValue_(value)
        self.enable(self.minValue != self.maxValue)

    @property
    def maxValue(self):
        return self._nsObject.maxValue()

    @maxValue.setter
    def maxValue(self, value):
        self._nsObject.setMaxValue_(value)
        self.enable(self.minValue != self.maxValue)


_minimalSpaceBox = 12


def addBoundingBoxes(glyphs):
    for gi in glyphs:
        if gi.path.elementCount():
            gi.bounds = offsetRect(rectFromNSRect(gi.path.controlPointBounds()), *gi.pos)
        else:
            # Empty shape, let's make a bounding box so we can visualize it anyway
            x, y = gi.pos
            if glyphs.vertical:
                xMin = x - glyphs.unitsPerEm
                xMax = x + glyphs.unitsPerEm * 1.5
                if abs(gi.ay) >= _minimalSpaceBox:
                    # gi.dy and gi.ay are negative
                    yMax = y - gi.dy
                    yMin = yMax + gi.ay
                else:
                    yMin = y - _minimalSpaceBox / 2
                    yMax = y + _minimalSpaceBox / 2
            else:
                if abs(gi.ax) >= _minimalSpaceBox:
                    xMin = x
                    xMax = x + gi.ax
                else:
                    xMin = x - _minimalSpaceBox / 2
                    xMax = x + _minimalSpaceBox / 2
                yMin = y - glyphs.unitsPerEm
                yMax = y + glyphs.unitsPerEm * 1.5
            gi.bounds = (xMin, yMin, xMax, yMax)


def _tagFromMenuItem(title):
    if not title:
        return None
    tag = title.split()[0]
    if len(tag) < 4:
        tag += " " * (4 - len(tag))
    return tag


def _remapArrowKeys(event, mapping):
    chars = mapping.get(event.characters(), event.characters())
    event = AppKit.NSEvent.keyEventWithType_location_modifierFlags_timestamp_windowNumber_context_characters_charactersIgnoringModifiers_isARepeat_keyCode_(
        event.type(), event.locationInWindow(), event.modifierFlags(), event.timestamp(),
        event.windowNumber(), event.context(), chars, chars, event.isARepeat(), event.keyCode())
    return event


def transposeArrowKeyEvent(event):
    transposeMap = {
        AppKit.NSUpArrowFunctionKey: AppKit.NSLeftArrowFunctionKey,
        AppKit.NSDownArrowFunctionKey: AppKit.NSRightArrowFunctionKey,
        AppKit.NSLeftArrowFunctionKey: AppKit.NSUpArrowFunctionKey,
        AppKit.NSRightArrowFunctionKey: AppKit.NSDownArrowFunctionKey,
    }
    return _remapArrowKeys(event, transposeMap)


def flipArrowKeyEvent(event):
    flipMap = {
        AppKit.NSUpArrowFunctionKey: AppKit.NSDownArrowFunctionKey,
        AppKit.NSDownArrowFunctionKey: AppKit.NSUpArrowFunctionKey,
        AppKit.NSLeftArrowFunctionKey: AppKit.NSRightArrowFunctionKey,
        AppKit.NSRightArrowFunctionKey: AppKit.NSLeftArrowFunctionKey,
    }
    return _remapArrowKeys(event, flipMap)
