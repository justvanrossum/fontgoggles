import asyncio
from collections import defaultdict, namedtuple
import contextlib
import io
import logging
import os
import pathlib
import time
import traceback
import unicodedata2 as unicodedata
import AppKit
import objc
from vanilla import (ActionButton, CheckBox, EditText, Group, List, PopUpButton, SplitView,
                     TextBox, TextEditor, VanillaBaseControl, Window, HorizontalLine)
from vanilla.dialogs import getFile
from fontTools.misc.arrayTools import offsetRect
from fontgoggles.font import mergeAxes, mergeScriptsAndLanguages, mergeStylisticSetNames
from fontgoggles.font.baseFont import GlyphsRun
from fontgoggles.mac.aligningScrollView import AligningScrollView
from fontgoggles.mac.featureTagGroup import FeatureTagGroup
from fontgoggles.mac.fileObserver import getFileObserver
from fontgoggles.mac.fontList import FontList, fontItemMinimumSize, fontItemMaximumSize, makeUndoProxy
from fontgoggles.mac.misc import ClassNameIncrementer, makeTextCell
from fontgoggles.mac.sliderGroup import SliderGroup, SliderPlus
from fontgoggles.mac.vanillaTabsOld import Tabs
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
    ("Automatic, with BiDi and Segmentation", None),
    ("Automatic, w/o BiDi and Segmentation", None),
    ("Left-to-Right", "LTR"),
    ("Right-to-Left", "RTL"),
    (None, None),  # separator
    ("Top-to-Bottom", "TTB"),
    ("Bottom-to-Top", "BTT"),
]
directionOptions = [label for label, direction in directionPopUpConfig]
directionSettings = [direction for label, direction in directionPopUpConfig]

alignmentOptionsHorizontal = ["Automatic", "Left", "Right", "Center"]
alignmentValuesHorizontal = [None, "left", "right", "center"]

alignmentOptionsVertical = ["Automatic", "Top", "Bottom", "Center"]
alignmentValuesVertical = [None, "top", "bottom", "center"]

feaVarTabLabels = ["Features", "Variations", "Options"]
feaVarTabValues = [v.lower() for v in feaVarTabLabels]


AxisSliderInfo = namedtuple("AxisSliderInfo", ["label", "minValue", "defaultValue", "maxValue", "hidden"])


class FGMainWindowController(AppKit.NSWindowController, metaclass=ClassNameIncrementer):

    def __new__(cls, project):
        return cls.alloc().init()

    def __init__(self, project):
        self.project = project
        self.projectProxy = makeUndoProxy(self.project, self._projectFontsChanged)
        self.observedPaths = {}
        self._callbackRecursionLock = 0
        self._previouslySingleSelectedItem = None

        characterListGroup = self.setupCharacterListGroup()
        glyphListGroup = self.setupGlyphListGroup()
        fontListGroup = self.setupFontListGroup()
        sidebarGroup = self.setupSidebarGroup()

        glyphListSize = self.project.uiSettings.glyphListSize
        paneDescriptors = [
            dict(view=glyphListGroup, identifier="glyphList", canCollapse=True,
                 size=glyphListSize, minSize=80, resizeFlexibility=False),
            dict(view=fontListGroup, identifier="fontList", canCollapse=False,
                 size=200, minSize=160),
        ]
        subSplitView = MySplitView((0, 0, 0, 0), paneDescriptors, dividerStyle="thin")
        if not self.project.uiSettings.glyphListVisible:
            subSplitView.togglePane("glyphList")
        self.subSplitView = subSplitView

        characterListSize = self.project.uiSettings.characterListSize
        paneDescriptors = [
            dict(view=characterListGroup, identifier="characterList", canCollapse=True,
                 size=characterListSize, minSize=98, resizeFlexibility=False),
            dict(view=subSplitView, identifier="subSplit", canCollapse=False),
            dict(view=sidebarGroup, identifier="formattingOptions", canCollapse=True,
                 size=sidebarWidth, minSize=sidebarWidth, maxSize=sidebarWidth,
                 resizeFlexibility=False),
        ]
        mainSplitView = MySplitView((0, 0, 0, 0), paneDescriptors, dividerStyle="thin")
        if not self.project.uiSettings.characterListVisible:
            mainSplitView.togglePane("characterList")
        if not self.project.uiSettings.formattingOptionsVisible:
            mainSplitView.togglePane("formattingOptions")

        self.w = Window((1400, 700), "FontGoggles", minSize=(900, 500), autosaveName="FontGogglesWindow",
                        fullScreenMode="primary")
        self.restoreWindowPosition(self.project.uiSettings.windowPosition)

        self.w.mainSplitView = mainSplitView
        self.w.open()

        # this removes a one pixel border at the top of the list view headers
        _tweakFrameHeight(self.glyphList._nsObject)
        _tweakFrameHeight(self.characterList._nsObject)

        self.w._window.setWindowController_(self)
        self.w._window.makeFirstResponder_(fontListGroup.textEntry.nsTextView)
        self.setWindow_(self.w._window)

        self.textEntry.set(self.project.textSettings.text)
        self.textEntryChangedCallback(self.textEntry)
        self.w.bind("close", self._windowCloseCallback)
        self.updateFileObservers()
        self.loadFonts(shouldRestoreSettings=True)

    @objc.python_method
    @suppressAndLogException
    def _windowCloseCallback(self, sender):
        obs = getFileObserver()
        for path in self.observedPaths:
            obs.removeObserver(path, self._fileChanged)
        self.__dict__.clear()

    def windowTitleForDocumentDisplayName_(self, displayName):
        return f"FontGoggles — {displayName}"

    @suppressAndLogException
    def syncUISettingsWithProject(self):
        # Called by FGDocument just before save
        textSettings = self.project.textSettings
        uiSettings = self.project.uiSettings

        textSettings.text = self.textEntry.get()
        textSettings.textFilePath = self.textEntry.textFilePath
        textSettings.textFileIndex = self.textEntry.textFileIndex

        (x, y), (w, h) = self.w._window.frame()
        uiSettings.windowPosition = [x, y, w, h]
        uiSettings.fontListItemSize = self.fontList.itemSize
        uiSettings.fontListShowFontFileName = self.fontList.showFontFileName

        uiSettings.characterListVisible = self.w.mainSplitView.isPaneReallyVisible("characterList")
        uiSettings.characterListSize = self.w.mainSplitView.paneSize("characterList")
        uiSettings.glyphListVisible = self.subSplitView.isPaneReallyVisible("glyphList")
        uiSettings.glyphListSize = self.subSplitView.paneSize("glyphList")
        uiSettings.compileOutputVisible = self.fontListSplitView.isPaneReallyVisible("compileOutput")
        uiSettings.compileOutputSize = self.fontListSplitView.paneSize("compileOutput")
        uiSettings.formattingOptionsVisible = self.w.mainSplitView.isPaneReallyVisible("formattingOptions")
        uiSettings.feaVarTabSelection = feaVarTabValues[self.feaVarTabs.get()]
        uiSettings.showHiddenAxes = self.variationsGroup.axisSliders.showHiddenAxes

    @objc.python_method
    def restoreWindowPosition(self, windowPosition):
        if not windowPosition:
            return
        window = self.w._window
        x, y, w, h = windowPosition
        window.setFrame_display_(((x, y), (w, h)), False)
        sw, sh = window.screen().visibleFrame().size
        w = min(w, sw)
        h = min(h, sh)
        window.setFrame_display_(((x, y), (w, h)), True)

    @objc.python_method
    def setupCharacterListGroup(self):
        group = Group((0, 0, 0, 0))
        columnDescriptions = [
            dict(title="char", width=30, typingSensitive=True, cell=makeTextCell("center")),
            dict(title="unicode", width=63, cell=makeTextCell("right")),
            dict(title="unicode name", width=200, minWidth=200, maxWidth=400, key="unicodeName",
                 cell=makeTextCell("left", "truncmiddle")),
            dict(title="script", width=50),
            dict(title="dir.", key="dir", width=36),
            dict(title="bidi lvl.", key="bidiLevel", width=40, cell=makeTextCell("right")),
            dict(title="index", width=36, cell=makeTextCell("right")),
        ]
        self.characterList = List((0, 0, 0, 0), [],
                                  columnDescriptions=columnDescriptions,
                                  allowsSorting=False, drawFocusRing=False, rowHeight=20,
                                  selectionCallback=self.characterListSelectionChangedCallback)
        self.characterList._tableView.setAllowsColumnSelection_(True)
        self.characterList._tableView.setDelegate_(self)
        self.characterList._nsObject.setBorderType_(AppKit.NSNoBorder)
        if hasattr(AppKit, "NSTableViewStylePlain") and hasattr(self.characterList.getNSTableView(), "setStyle_"):
            self.characterList.getNSTableView().setStyle_(AppKit.NSTableViewStylePlain)
            self.characterList.getNSTableView().setIntercellSpacing_((3, 2))
        group.characterList = self.characterList
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
        self.glyphList = List((0, 0, 0, 0), [],
                              columnDescriptions=columnDescriptions,
                              allowsSorting=False, drawFocusRing=False,
                              rowHeight=20,
                              selectionCallback=self.glyphListSelectionChangedCallback)
        self.glyphList._tableView.setAllowsColumnSelection_(True)
        self.glyphList._tableView.setDelegate_(self)
        self.glyphList._nsObject.setBorderType_(AppKit.NSNoBorder)
        if hasattr(AppKit, "NSTableViewStylePlain") and hasattr(self.glyphList.getNSTableView(), "setStyle_"):
            self.glyphList.getNSTableView().setStyle_(AppKit.NSTableViewStylePlain)
            self.glyphList.getNSTableView().setIntercellSpacing_((3, 2))
        group.glyphList = self.glyphList
        return group

    @objc.python_method
    def setupFontListGroup(self):
        group = Group((0, 0, 0, 0))
        textFilePath = self.project.textSettings.textFilePath
        textFileIndex = self.project.textSettings.textFileIndex
        if textFilePath and not os.path.exists(textFilePath):
            print("text file not found:", textFilePath)
            textFilePath = None
        self.textEntry = TextEntryGroup((0, 0, 0, 40), textFilePath=textFilePath,
                                        callback=self.textEntryChangedCallback)
        if textFilePath and textFileIndex:
            self.textEntry.setTextFileIndex(textFileIndex, wrapAround=False)
        itemSize = self.project.uiSettings.fontListItemSize
        vertical = self.project.textSettings.direction in {"TTB", "BTT"}
        self.fontList = FontList(self.project, self.projectProxy, 300, itemSize, vertical=vertical,
                                 relativeFontSize=self.project.textSettings.relativeFontSize,
                                 relativeHBaseline=self.project.textSettings.relativeHBaseline,
                                 relativeVBaseline=self.project.textSettings.relativeVBaseline,
                                 relativeMargin=self.project.textSettings.relativeMargin,
                                 showFontFileName=self.project.uiSettings.fontListShowFontFileName,
                                 selectionChangedCallback=self.fontListSelectionChangedCallback,
                                 glyphSelectionChangedCallback=self.fontListGlyphSelectionChangedCallback,
                                 arrowKeyCallback=self.fontListArrowKeyCallback)
        self._fontListScrollView = AligningScrollView((0, 0, 0, 0), self.fontList, drawBackground=True,
                                                      forwardDragAndDrop=True)
        self._fontListScrollView._nsObject.setBorderType_(AppKit.NSNoBorder)

        self.compileOutput = OutputText((0, 0, 0, 0))
        self.compileOutput._nsObject.setBorderType_(AppKit.NSNoBorder)

        compileOutputSize = self.project.uiSettings.compileOutputSize
        paneDescriptors = [
            dict(view=self._fontListScrollView, identifier="fontList", canCollapse=False,
                 size=230, minSize=150),
            dict(view=self.compileOutput, identifier="compileOutput", canCollapse=True,
                 size=compileOutputSize, minSize=30, resizeFlexibility=False),
        ]
        self.fontListSplitView = MySplitView((0, 41, 0, 0), paneDescriptors, dividerStyle="thin",
                                             isVertical=False)
        if not self.project.uiSettings.compileOutputVisible:
            self.fontListSplitView.togglePane("compileOutput")

        group.textEntry = self.textEntry
        group.divider = HorizontalLine((0, 40, 0, 1))
        group.fontListSplitView = self.fontListSplitView
        return group

    @objc.python_method
    def setupSidebarGroup(self):
        group = Group((0, 0, 0, 0))
        group.generalSettings = self.setupGeneralSettingsGroup()
        x, y, w, h = group.generalSettings.getPosSize()
        self.feaVarTabs = Tabs((0, h + 6, 0, 0), feaVarTabLabels)
        group.feaVarTabs = self.feaVarTabs
        group.feaVarTabs.set(feaVarTabValues.index(self.project.uiSettings.feaVarTabSelection))

        # Sidebar first tab
        featuresTab = group.feaVarTabs[0]
        self.featuresGroup = FeatureTagGroup(sidebarWidth - 6, {}, callback=self.featuresChanged)
        featuresTab.main = AligningScrollView((0, 0, 0, 0), self.featuresGroup, drawBackground=False,
                                              hasHorizontalScroller=False, autohidesScrollers=True,
                                              borderType=AppKit.NSNoBorder)

        # Sidebar second tab
        variationsTab = group.feaVarTabs[1]
        self.variationsGroup = Group((0, 0, 0, 0))

        self.variationsGroup.axisSliders = SliderGroup(sidebarWidth - 6, {},
                                                       callback=self.varLocationChanged,
                                                       showHiddenAxes=self.project.uiSettings.showHiddenAxes)

        self.variationsGroup.instances = LabeledView(
            # Position and instances gets updated as fonts are read
            (0, 0, 0, 20),
            "Instances:",
            PopUpButton, [],
            callback=self.varInstanceChanged,
        )

        # The content of the tab wrapping the axes sliders and instance dropdown
        variationsTab.main = AligningScrollView((0, 0, 0, 0), self.variationsGroup, drawBackground=False,
                                                hasHorizontalScroller=False, autohidesScrollers=True,
                                                borderType=AppKit.NSNoBorder)

        # Sidebar third tab
        optionsTab = group.feaVarTabs[2]
        relativeFontSize = self.project.textSettings.relativeFontSize * 100
        relativeBaseline = self.getRelativeBaselineValueForSlider()
        relativeMargin = self.project.textSettings.relativeMargin * 100
        y = 10
        optionsTab.relativeSizeSlider = SliderPlus((10, y, sidebarWidth - 26, 40), "Relative Size",
                                                   25, relativeFontSize, 125,
                                                   callback=self.relativeSizeChangedCallback)
        y += 50
        optionsTab.relativeBaselineSlider = SliderPlus((10, y, sidebarWidth - 26, 40), "Baseline",
                                                       0, relativeBaseline, 100,
                                                       callback=self.relativeBaselineChangedCallback)
        y += 50
        optionsTab.relativeMarginSlider = SliderPlus((10, y, sidebarWidth - 26, 40), "Margin",
                                                     0, relativeMargin, 100,
                                                     callback=self.relativeMarginChangedCallback)
        self.relativeBaselineSlider = optionsTab.relativeBaselineSlider
        y += 50
        optionsTab.enableColor = CheckBox((10, y, sidebarWidth - 26, 25), "Enable Color (COLR/CPAL)",
                                          value=self.project.textSettings.enableColor,
                                          callback=self.enableColorChangedCallback)
        y += 35

        return group

    def getRelativeBaselineValueForSlider(self):
        if self.project.textSettings.direction in {"TTB", "BTT"}:
            return self.project.textSettings.relativeVBaseline * 100
        else:
            return self.project.textSettings.relativeHBaseline * 100

    def setupGeneralSettingsGroup(self):
        group = Group((0, 0, 0, 0))
        y = 10

        textSettings = self.project.textSettings
        storedDirection = textSettings.direction

        directions = [label if label is not None else AppKit.NSMenuItem.separatorItem() for label in directionOptions]

        self.directionPopUp = LabeledView(
            (10, y, -10, 40), "Direction/orientation:",
            PopUpButton, directions,
            callback=self.directionPopUpCallback,
        )
        if storedDirection:
            self.directionPopUp.set(directionSettings.index(storedDirection))
        else:
            if not textSettings.shouldApplyBiDi:
                self.directionPopUp.set(1)
        group.directionPopUp = self.directionPopUp
        y += 50

        vertical = self.project.textSettings.direction in {"TTB", "BTT"}
        if vertical:
            alignmentOptions = alignmentOptionsVertical
            alignmentValues = alignmentValuesVertical
        else:
            alignmentOptions = alignmentOptionsHorizontal
            alignmentValues = alignmentValuesHorizontal
        self.alignmentPopup = LabeledView(
            (10, y, -10, 40), "Visual alignment:",
            PopUpButton, alignmentOptions,
            callback=self.alignmentChangedCallback,
        )
        self.alignmentPopup.set(alignmentValues.index(self.project.textSettings.alignment))

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
        self.setLanguagesFromScript()
        return group

    def updateFileObservers(self):
        obs = getFileObserver()
        newObservedPaths = defaultdict(list)
        for fontItemInfo in self.project.fonts:
            fontPath = fontItemInfo.fontKey[0]
            if not fontPath.exists():
                # We can't observe a non-existing path. This can happen
                # if the project file contains a wrong source path.
                # We don't want to stop loading other fonts that do have a
                # correct path so we won't complain here.
                continue
            newObservedPaths[fontPath].append(fontItemInfo)
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

    @objc.python_method
    @suppressAndLogException
    def _fileChanged(self, oldPath, newPath, wasModified):
        # This gets called by the file observer, when a file changed on disk.
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

    @objc.python_method
    @suppressAndLogException
    def _projectFontsChanged(self, changeSet):
        # This gets called by the undo manager, upon performing undo or redo.
        if any(change.op == "remove" for change in changeSet):
            self.fontList.purgeFontItems()
            self.project.purgeFonts()
        fontItemsNeedingTextUpdate = self.fontList.refitFontItems()
        self.fontList.selection = self.project.fontSelection
        self.fontList.ensureFirstResponder()

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
    async def loadFonts(self, shouldRestoreSettings=False):
        """This loads fonts that aren't yet loaded, and updates all information
        regarding features, scripts/languages and variations.
        """
        if not hasattr(self, "fontList"):
            # Window closed before we got to run
            return ()
        coros = []
        for fontItemInfo, fontItem in self.iterFontItemInfoAndItems():
            if fontItemInfo.font is None or fontItemInfo.wantsReload:
                coros.append(self._loadFont(fontItemInfo, fontItem))
        await asyncio.gather(*coros)
        self._updateSidebarItems(*self._gatherSidebarInfo(self.project.fonts))
        if shouldRestoreSettings:
            self._updateSidebarSettings()
        else:
            self.setLanguagesFromScript()  # update the available languages
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
            fontItemInfo.unload()  # ensure we start with a clean slate next time
            fontItem.glyphs = GlyphsRun(0, 1000, False)
            fontItem.writeCompileOutput(f"{e!r}\n")
        except asyncio.CancelledError:
            fontItemInfo.unload()  # ensure we start with a clean slate next time
            raise
        except Exception:
            fontItemInfo.unload()  # ensure we start with a clean slate next time
            fontItem.glyphs = GlyphsRun(0, 1000, False)
            fontItem.writeCompileOutput(traceback.format_exc())
        else:
            self.setFontItemText(fontItemInfo, fontItem)
            self.growFontListFromItem(fontItem)
            fontItem.setFontKey(fontItemInfo.fontKey, fontItemInfo.font.nameInCollection)

    @staticmethod
    def _gatherSidebarInfo(fonts):
        allFeatureTagsGSUB = set()
        allFeatureTagsGPOS = set()
        allAxes = []
        allInstances = [("No instance selected", {})]
        allScriptsAndLanguages = []
        allStylisticSetNames = []
        for fontItemInfo in fonts:
            font = fontItemInfo.font
            if font is None:
                continue
            allFeatureTagsGSUB.update(font.featuresGSUB)
            allFeatureTagsGPOS.update(font.featuresGPOS)
            allAxes.append(font.axes)
            allScriptsAndLanguages.append(font.scripts)
            allStylisticSetNames.append(font.stylisticSetNames)
            allInstances.extend([i for i in font.instances if i not in allInstances])
        allAxes = mergeAxes(*allAxes)
        allScriptsAndLanguages = mergeScriptsAndLanguages(*allScriptsAndLanguages)
        allStylisticSetNames = mergeStylisticSetNames(*allStylisticSetNames)
        return allFeatureTagsGSUB, allFeatureTagsGPOS, allAxes, allInstances, \
            allScriptsAndLanguages, allStylisticSetNames

    @objc.python_method
    def _updateSidebarItems(self, allFeatureTagsGSUB, allFeatureTagsGPOS, allAxes, allInstances,
                            allScriptsAndLanguages, allStylisticSetNames):
        self.featuresGroup.setTags({"GSUB": allFeatureTagsGSUB, "GPOS": allFeatureTagsGPOS},
                                   allStylisticSetNames)
        sliderInfo = {}
        for tag, axis in allAxes.items():
            name = sorted(axis['name'])[0]
            if axis["hidden"]:
                label = f"{name} ({tag}, hidden)"
            else:
                label = f"{name} ({tag})"
            if len(axis['name']) > 1:
                label += " <multiple names>"
            sliderInfo[tag] = AxisSliderInfo(
                label,
                axis["minValue"],
                axis["defaultValue"],
                axis["maxValue"],
                axis["hidden"],
            )

        # The axis order easily becomes a mess when multiple fonts are loaded.
        # Sort by (not isAxisRegistered, label.lower()), but keep it a dict.
        # Downside: we no longer see the axes in the order defined by the font.
        def sorter(keyValue):
            tag, axisInfo = keyValue
            isAxisRegistered = tag == tag.lower()  # all lowercase tags are registered axes
            return not isAxisRegistered, axisInfo.label.lower()
        sliderInfo = {k: v for k, v in sorted(sliderInfo.items(), key=sorter)}

        self.variationsGroup.axisSliders.setSliderInfo(sliderInfo)
        self.variationsGroup.instances.setPosSize((0, self.variationsGroup.axisSliders.getPosSize()[3], 0, 40)),
        self.variationsGroup.instances.setItems([i[0] for i in allInstances])

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

    def _updateSidebarSettings(self):
        scriptTags = [_tagFromMenuItem(item, "Automatic") for item in self.scriptsPopup.getItems()]
        self.scriptsPopup.set(scriptTags.index(self.project.textSettings.script))
        self.setLanguagesFromScript()
        languageTags = [_tagFromMenuItem(item, "dflt") for item in self.languagesPopup.getItems()]
        self.languagesPopup.set(languageTags.index(self.project.textSettings.language))
        self.featuresGroup.set(self.project.textSettings.features)
        self.variationsGroup.axisSliders.set(self.project.textSettings.varLocation)

    def iterFontItems(self):
        return self.fontList.iterFontItems()

    def iterFontItemInfoAndItems(self):
        return self.fontList.iterFontItemInfoAndItems()

    @objc.python_method
    @asyncTaskAutoCancel
    async def textEntryChangedCallback(self, sender, updateCharacterList=True):
        if not hasattr(self, "directionPopUp"):
            # Our window already closed, and our poor async task is too
            # late. Nothing left to do.
            return
        self.textInfo = TextInfo(sender.get())
        self.textInfo.shouldApplyBiDi = self.project.textSettings.shouldApplyBiDi
        self.textInfo.directionOverride = self.project.textSettings.direction
        self.textInfo.scriptOverride = self.project.textSettings.script
        self.textInfo.languageOverride = self.project.textSettings.language
        if self.project.textSettings.alignment is not None:
            align = self.project.textSettings.alignment
        else:
            align = self.textInfo.suggestedAlignment

        if align != self.fontList.align:
            self.alignmentChangedCallback(self.alignmentPopup)
        else:
            self.updateTextEntryAlignment(align)

        if updateCharacterList:
            # Immediately reset selection, so that delayed async clients
            # won't get a stale selection.
            self.characterList.setSelection([])
            self.updateCharacterList(delay=0.05)
        else:
            charSelection = self.characterList.getSelection()
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
        if not updateCharacterList:
            self.characterList.setSelection(charSelection)
            self.characterListSelectionChangedCallback(self.characterList)

    @objc.python_method
    def setFontItemText(self, fontItemInfo, fontItem):
        font = fontItemInfo.font
        if font is None:
            return
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            glyphs = font.getGlyphRunFromTextInfo(self.textInfo,
                                                  features=self.project.textSettings.features,
                                                  varLocation=self.project.textSettings.varLocation,
                                                  colorLayers=self.project.textSettings.enableColor)
        stderr = stderr.getvalue()
        if stderr:
            fontItem.writeCompileOutput(stderr)

        addBoundingBoxes(glyphs)
        fontItem.glyphs = glyphs
        charSelection = self.characterList.getSelection()
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

    @objc.python_method
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

    @objc.python_method
    @asyncTaskAutoCancel
    async def updateCharacterList(self, selection=None, delay=0):
        if not hasattr(self, "project"):
            # Window closed before we got to run
            return
        if delay:
            # add a slight delay, so we won't do a lot of work when there's fast typing
            await asyncio.sleep(delay)
        uniListData = []
        for segmentText, segmentScript, segmentBiDiLevel, firstCluster in self.textInfo._segments:
            for index, char in enumerate(segmentText, firstCluster):
                uniListData.append(
                    dict(index=index, char=char, unicode=f"U+{ord(char):04X}",
                         unicodeName=unicodedata.name(char, "?"), script=segmentScript,
                         bidiLevel=segmentBiDiLevel, dir=["LTR", "RTL"][segmentBiDiLevel % 2])
                )
        self.characterList.set(uniListData)
        if selection is not None:
            self.characterList.setSelection(selection)

    @objc.python_method
    def fontListSelectionChangedCallback(self, sender):
        fontItem = sender.getSingleSelectedItem()
        if self._previouslySingleSelectedItem is not None:
            self._previouslySingleSelectedItem.setAuxillaryOutput(None)
        if fontItem is not None:
            glyphs = fontItem.glyphs
            self.updateCharacterListSelection(fontItem)
            output = fontItem.getCompileOutput()
            self.compileOutput.set(output)
            fontItem.setAuxillaryOutput(self.compileOutput)

            if output and not self.fontListSplitView.isPaneReallyVisible("compileOutput"):
                # This may be annoying if warnings are common and need to be ignored
                # more. For now, let's make sure the user sees all warnings/errors.
                self.fontListSplitView.togglePane("compileOutput")
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
            self.characterList.setSelection([])
            return
        if selectedFontItem.glyphs is not None:
            charIndices = selectedFontItem.glyphs.mapGlyphsToChars(selectedFontItem.selection)
            glyphNames = selectedFontItem.glyphs.glyphNames
            glyphIndices = set(selectedFontItem.selection)
        else:
            charIndices = []
            glyphNames = []
            glyphIndices = set()

        with self.blockCallbackRecursion():
            for fontItem in self.iterFontItems():
                if fontItem is selectedFontItem:
                    self.glyphList.setSelection(fontItem.selection)
                    self.updateCharacterListSelection(fontItem)
                elif fontItem.glyphs is not None:
                    if fontItem.glyphs.glyphNames == glyphNames:
                        fontItem.selection = glyphIndices
                    else:
                        fontItem.selection = fontItem.glyphs.mapCharsToGlyphs(charIndices)

    @objc.python_method
    def fontListArrowKeyCallback(self, sender, event):
        if not self.fontList.vertical:
            event = transposeArrowKeyEvent(event)
        if len(self.glyphList) > 0:
            self.glyphList._nsObject.documentView().keyDown_(event)
        elif len(self.characterList) > 0:
            if not self.textInfo.shouldApplyBiDi:
                # Either automatic direction (as detected by HB) or explicit
                # reversal of direction
                if self.textInfo.direction in ("RTL", "BTT"):
                    event = flipArrowKeyEvent(event)
                self.characterList._nsObject.documentView().keyDown_(event)
            else:
                # BiDi processing is on, and we're looking at the original
                # text sequence (before BiDi processing). We convert our
                # selection to post-BiDi, base the new selection on that,
                # then convert back to pre-BiDi. This way we can key
                # through the glyphs by character, but in the order of the
                # glyphs.
                if event.characters() == AppKit.NSUpArrowFunctionKey:
                    direction = -1
                else:
                    direction = 1
                charSelection = self.characterList.getSelection()
                if not charSelection:
                    if direction == -1:
                        newCharselection = [len(self.characterList) - 1]
                    else:
                        newCharselection = [0]
                else:
                    charSelection = self.textInfo.mapToBiDi(charSelection)
                    if direction == -1:
                        newCharselection = [max(0, min(charSelection) - 1)]
                    else:
                        newCharselection = [min(len(self.characterList) - 1, max(charSelection) + 1)]
                newCharselection = self.textInfo.mapFromBiDi(newCharselection)
                if event.modifierFlags() & AppKit.NSEventModifierFlagShift:
                    newCharselection = set(newCharselection + self.characterList.getSelection())
                self.characterList.setSelection(newCharselection)
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
            glyphNames = selectedFontItem.glyphs.glyphNames
        else:
            charIndices = []
            glyphNames = []

        glyphIndices = set(glyphIndices)
        with self.blockCallbackRecursion():
            for fontItem in self.iterFontItems():
                if fontItem is selectedFontItem:
                    fontItem.selection = glyphIndices
                    self.updateCharacterListSelection(fontItem)
                elif fontItem.glyphs is not None:
                    if fontItem.glyphs.glyphNames == glyphNames:
                        fontItem.selection = glyphIndices
                    else:
                        fontItem.selection = fontItem.glyphs.mapCharsToGlyphs(charIndices)
        self.fontList.scrollGlyphSelectionToVisible()

    @objc.python_method
    def updateCharacterListSelection(self, fontItem):
        if fontItem.glyphs is None:
            return
        charIndices = fontItem.glyphs.mapGlyphsToChars(fontItem.selection)
        with self.blockCallbackRecursion():
            self.characterList.setSelection(charIndices)

    @objc.python_method
    def characterListSelectionChangedCallback(self, sender):
        if self._callbackRecursionLock:
            return
        selectedFontItem = self.fontList.getSingleSelectedItem()

        charIndices = set(sender.getSelection())

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

        self.project.textSettings.shouldApplyBiDi = popupValue == 0
        self.project.textSettings.direction = directionSettings[popupValue]

        vertical = int(directionSettings[popupValue] in {"TTB", "BTT"})
        self.alignmentPopup.setItems([alignmentOptionsHorizontal, alignmentOptionsVertical][vertical])
        self.fontList.vertical = vertical
        self.alignmentChangedCallback(self.alignmentPopup)
        self.textEntryChangedCallback(self.textEntry)
        self.relativeBaselineSlider.set(self.getRelativeBaselineValueForSlider())

    @objc.python_method
    @suppressAndLogException
    def alignmentChangedCallback(self, sender):
        values = [alignmentValuesHorizontal,
                  alignmentValuesVertical][self.fontList.vertical]
        align = values[sender.get()]
        self.project.textSettings.alignment = align
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

    @objc.python_method
    def scriptsPopupCallback(self, sender):
        self.project.textSettings.script = self.setLanguagesFromScript()
        self.project.textSettings.language = _tagFromMenuItem(self.languagesPopup.getItem(), "dflt")
        self.textEntryChangedCallback(self.textEntry, updateCharacterList=False)

    def setLanguagesFromScript(self):
        tag = _tagFromMenuItem(self.scriptsPopup.getItem(), "Automatic")
        if tag is None:
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
        return tag

    @objc.python_method
    def languagesPopupCallback(self, sender):
        tag = _tagFromMenuItem(self.languagesPopup.getItem(), "dflt")
        self.project.textSettings.language = tag
        self.textEntryChangedCallback(self.textEntry, updateCharacterList=False)

    @objc.python_method
    def featuresChanged(self, sender):
        self.project.textSettings.features = self.featuresGroup.get()
        self.textEntryChangedCallback(self.textEntry, updateCharacterList=False)

    @objc.python_method
    def varLocationChanged(self, sender):
        """Axis slider value changed"""
        _, _, _, allInstances, _, _ = self._gatherSidebarInfo(self.project.fonts)
        self.project.textSettings.varLocation = {k: v for k, v in sender.get().items() if v is not None}
        self.textEntryChangedCallback(self.textEntry, updateCharacterList=False)
        self.variationsGroup.instances.setItems([i[0] for i in allInstances])
        # Reset instance popup
        self.variationsGroup.instances.set(0)

    @objc.python_method
    def varInstanceChanged(self, sender):
        """Instance was selected from popup"""
        _, _, _, allInstances, _, _ = self._gatherSidebarInfo(self.project.fonts)
        self.project.textSettings.varLocation = {k: v for k, v in allInstances[sender.get()][1].items() if v is not None}
        self.textEntryChangedCallback(self.textEntry, updateCharacterList=False)
        self.variationsGroup.axisSliders.set(self.project.textSettings.varLocation)

    @objc.python_method
    def relativeSizeChangedCallback(self, sender):
        if not hasattr(self, "fontList"):
            # Happens when the window is closing and the text field of the slider has focus
            return
        self.fontList.relativeFontSize = self.project.textSettings.relativeFontSize = sender.get() / 100
        self.growOrShrinkFontList()

    @objc.python_method
    def relativeBaselineChangedCallback(self, sender):
        if not hasattr(self, "fontList"):
            # Happens when the window is closing and the text field of the slider has focus
            return
        value = sender.get() / 100
        if self.fontList.vertical:
            self.project.textSettings.relativeVBaseline = value
            self.fontList.relativeVBaseline = value
        else:
            self.project.textSettings.relativeHBaseline = value
            self.fontList.relativeHBaseline = value

    @objc.python_method
    def relativeMarginChangedCallback(self, sender):
        if not hasattr(self, "fontList"):
            # Happens when the window is closing and the text field of the slider has focus
            return
        self.fontList.relativeMargin = self.project.textSettings.relativeMargin = sender.get() / 100
        self.growOrShrinkFontList()

    @objc.python_method
    def enableColorChangedCallback(self, sender):
        self.project.textSettings.enableColor = bool(sender.get())
        self.textEntryChangedCallback(self.textEntry, updateCharacterList=False)

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

        if self.textEntry.nsTextView.alignment() == nsAlign:
            return

        fieldEditor = self.w._window.fieldEditor_forObject_(False, self.textEntry.nsTextView)
        hasFocus = fieldEditor.delegate() is self.textEntry.nsTextView
        if hasFocus:
            sel = fieldEditor.selectedRange()
            fieldEditor.setAlignment_(nsAlign)
            self.textEntry.nsTextView.setAlignment_(nsAlign)
            # Now we've lost focus, let's get it again
            self.w._window.makeFirstResponder_(self.textEntry.nsTextView)
            # Now we've lost the selection, let's restore it
            fieldEditor.setSelectedRange_(sel)
        else:
            self.textEntry.nsTextView.setAlignment_(nsAlign)

    def showCharacterList_(self, sender):
        self.w.mainSplitView.togglePane("characterList")

    def showGlyphList_(self, sender):
        self.subSplitView.togglePane("glyphList")

    def showCompileOutput_(self, sender):
        self.fontListSplitView.togglePane("compileOutput")

    def showFormattingOptions_(self, sender):
        self.w.mainSplitView.togglePane("formattingOptions")

    def showFontFileName_(self, sender):
        self.fontList.showFontFileName = not self.fontList.showFontFileName

    @objc.python_method
    @suppressAndLogException
    def validateMenuItem_(self, sender):
        action = sender.action()
        title = sender.title()
        isVisible = None
        findReplace = ["Hide", "Show"]
        if action == "showCharacterList:":
            isVisible = self.w.mainSplitView.isPaneReallyVisible("characterList")
        elif action == "showGlyphList:":
            isVisible = self.subSplitView.isPaneReallyVisible("glyphList")
        elif action == "showCompileOutput:":
            isVisible = self.fontListSplitView.isPaneReallyVisible("compileOutput")
        elif action == "showFormattingOptions:":
            isVisible = self.w.mainSplitView.isPaneReallyVisible("formattingOptions")
        elif action == "showFontFileName:":
            isVisible = self.fontList.showFontFileName
        elif action in ("previousTextLine:", "nextTextLine:"):
            return bool(self.textEntry.textFilePath)
        elif action == "copy:":
            return self.w._window.firstResponder() in (self.glyphList._tableView,
                                                       self.characterList._tableView)
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

    def loadTextFile_(self, sender):
        self.textEntry.loadTextFileCallback(sender)

    def previousTextLine_(self, sender):
        self.textEntry.previousTextLine()

    def nextTextLine_(self, sender):
        self.textEntry.nextTextLine()

    def tableView_didClickTableColumn_(self, tableView, column):
        self.w._window.makeFirstResponder_(tableView)
        listView = tableView.vanillaWrapper()
        listView._selectionCallback(listView)

    @suppressAndLogException
    def copy_(self, sender):
        tableView = self.w._window.firstResponder()
        if not isinstance(tableView, AppKit.NSTableView):
            return
        listView = tableView.vanillaWrapper()
        colIndices = list(tableView.selectedColumnIndexes())
        rowIndices = list(tableView.selectedRowIndexes())
        if colIndices:
            rowIndices = range(len(listView))
            keys = [tableView.tableColumns()[i].identifier() for i in colIndices]
        else:
            keys = [col.identifier() for col in tableView.tableColumns()]

        # Make tab-separated text from the selection
        text = "\n".join("\t".join(str(listView[i].get(k, "")) for k in keys)
                         for i in rowIndices)
        if text:
            pb = AppKit.NSPasteboard.generalPasteboard()
            pb.clearContents()
            pb.declareTypes_owner_([AppKit.NSPasteboardTypeString], None)
            pb.setString_forType_(text, AppKit.NSPasteboardTypeString)


def _tweakFrameHeight(view):
    frame = view.frame()
    frame.size.height += 1
    view.setFrame_(frame)


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


class TextEntryGroup(Group):

    def __init__(self, posSize, textFilePath=None, callback=None):
        super().__init__(posSize)
        textRightMargin = 76
        self.textEntry = EditText((10, 8, -textRightMargin, 25), "", callback=callback)
        self.textFileStepper = Stepper((-textRightMargin + 5, 8, 12, 25), 0, 0, 1, callback=self.stepperCallback)
        items = [
            dict(title="Load Text File...", callback=self.loadTextFileCallback),
            dict(title="Forget Text File", callback=self.forgetTextFileCallback),
            # TODO: Reveal in Finder
        ]
        self.textFileMenuButton = ActionButton((-textRightMargin + 25, 8, -10, 25), items)
        # TODO: keep a list of (10?) recent items
        self.textFilePath = None
        self.setTextFile(textFilePath)
        self.textFileIndex = 0

    def _breakCycles(self):
        super()._breakCycles()
        if self.textFilePath is not None:
            obs = getFileObserver()
            obs.removeObserver(self.textFilePath, self.textFileChanged)

    def get(self):
        return self.textEntry.get()

    def set(self, value):
        self.textEntry.set(value)

    @property
    def nsTextView(self):
        return self.textEntry._nsObject

    def loadTextFileCallback(self, sender):
        window = self._nsObject.window()
        getFile("Please select a text file",
                fileTypes=["txt"], parentWindow=window,
                resultCallback=self.getFileCompiletionHandler)

    def getFileCompiletionHandler(self, result):
        self.setTextFile(result[0])

    def forgetTextFileCallback(self, sender):
        self.setTextFile(None)

    def textFileChanged(self, oldPath, newPath, wasModified):
        if newPath is not None:
            self.textFilePath = newPath
        if wasModified:
            self.setTextFile(self.textFilePath, resetIndex=False)

    def setTextFile(self, path, resetIndex=True):
        if path != self.textFilePath:
            if path is not None:
                path = os.path.normpath(path)
            if self.textFilePath is not None:
                obs = getFileObserver()
                obs.removeObserver(self.textFilePath, self.textFileChanged)
        if path is None:
            self.textFilePath = None
            self.lines = [self.textEntry.get()]
        else:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                self.lines = f.read().splitlines()
            if path != self.textFilePath:
                self.textFilePath = path
                obs = getFileObserver()
                obs.addObserver(self.textFilePath, self.textFileChanged)
        self.textFileStepper.maxValue = len(self.lines) - 1 if self.lines else 0
        if resetIndex:
            self.textFileStepper.set(self.textFileStepper.maxValue)
            self.setTextFileIndex(0)
        else:
            self.setTextFileIndex(self.textFileIndex, wrapAround=False)

    def previousTextLine(self):
        self.setTextFileIndex(self.textFileIndex - 1)
        self.updateStepper()

    def nextTextLine(self):
        self.setTextFileIndex(self.textFileIndex + 1)
        self.updateStepper()

    def setTextFileIndex(self, index, wrapAround=True):
        if self.lines:
            if wrapAround:
                index = index % len(self.lines)
            else:
                index = min(index, len(self.lines) - 1)
            line = self.lines[index]
            self.textFileIndex = index
        else:
            line = ""
            self.textFileIndex = 0
        self.textEntry.set(line)
        self.textEntry._target.callback(self.textEntry)

    def stepperCallback(self, sender):
        self.setTextFileIndex(len(self.lines) - 1 - sender.get())

    def updateStepper(self):
        self.stepper.set(len(self.lines) - 1 - self.textFileIndex)


class MySplitView(SplitView):

    def isPaneReallyVisible(self, paneIdentifier):
        return not self.isPaneVisible(paneIdentifier)

    def paneSize(self, paneIdentifier):
        view = self._identifierToPane[paneIdentifier]["view"]
        w, h = view._nsObject.frame().size
        if self._nsObject.isVertical():
            return w
        else:
            return h


_minimalSpaceBox = 12


def addBoundingBoxes(glyphs):
    for gi in glyphs:
        bounds = gi.glyphDrawing.bounds
        if bounds is not None:
            gi.bounds = offsetRect(bounds, *gi.pos)
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


def _tagFromMenuItem(title, defaultTitle=None):
    if not title:
        return None
    tag = title.split()[0]
    if len(tag) < 4:
        tag += " " * (4 - len(tag))
    if tag == defaultTitle:
        tag = None
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
