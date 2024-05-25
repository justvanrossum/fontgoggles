import io
import math
import logging
import os
import pathlib
from types import SimpleNamespace
import objc
import AppKit
from objc import super

from vanilla import Group, ProgressSpinner, TextBox, VanillaBaseObject
from jundo import UndoManager
from fontTools.misc.arrayTools import offsetRect, scaleRect, unionRect
from fontgoggles.font import defaultSortSpec, sniffFontType, sortedFontPathsAndNumbers
from fontgoggles.mac.drawing import (
    blendRGBA,
    nsColorFromRGBA,
    nsRectFromRect,
    rgbaFromNSColor,
    rectFromNSRect,
    scale,
    translate
)
from fontgoggles.mac.misc import textAlignments
from fontgoggles.misc.decorators import suppressAndLogException, asyncTaskAutoCancel
from fontgoggles.misc.properties import delegateProperty, hookedProperty, cachedProperty
from fontgoggles.misc.rectTree import RectTree


FGPasteboardTypeFileURL = getattr(AppKit, "NSPasteboardTypeFileURL", None)
if FGPasteboardTypeFileURL is None:
    # Happens when building/running on macOS 10.10. The value just works, though.
    FGPasteboardTypeFileURL = "public.file-url"
FGPasteboardTypeFontNumber = "com.github.justvanrossum.fontgoggles.fontnumber"
FGPasteboardTypeFontItemIdentifier = "com.github.justvanrossum.fontgoggles.fontitemidentifier"

fontItemMinimumSize = 60
fontItemMaximumSize = 1500


supportedFormatsString = """
Supported formats:
• .designspace, .ufo, .ufoz
• .ttf, .otf, .woff, .woff2, .ttx
• .ttc, .otc
"""


def makeUndoProxy(model, changeMonitor=None):
    um = UndoManager(changeMonitor)
    return um.setModel(model)


def recordChanges(proxy, **kwargs):
    return proxy._undoManager.changeSet(**kwargs)


def undoChanges(proxy):
    proxy._undoManager.undo()


def redoChanges(proxy):
    proxy._undoManager.redo()


def undoInfo(proxy):
    return proxy._undoManager.undoInfo()


def redoInfo(proxy):
    return proxy._undoManager.redoInfo()


class FGFontListView(AppKit.NSView):

    def init(self):
        self = super().init()
        self.registerForDraggedTypes_([FGPasteboardTypeFileURL])
        return self

    def acceptsFirstResponder(self):
        return True

    def becomeFirstResponder(self):
        return True

    def mouseDown_(self, event):
        self.vanillaWrapper().mouseDown(event)

    def mouseDragged_(self, event):
        self.vanillaWrapper().mouseDragged(event)

    def mouseUp_(self, event):
        self.vanillaWrapper().mouseUp(event)

    def keyDown_(self, event):
        if not self.vanillaWrapper().keyDown(event):
            super().keyDown_(event)

    def magnifyWithEvent_(self, event):
        if event.phase() in {AppKit.NSEventPhaseBegan, AppKit.NSEventPhaseMayBegin}:
            self._originalItemSize = self.vanillaWrapper().itemSize
            self._magnification = 1.0
        centerPoint = self.convertPoint_fromView_(event.locationInWindow(), None)
        self._magnification += event.magnification()
        newItemSize = round(max(fontItemMinimumSize,
                                min(fontItemMaximumSize, self._originalItemSize * self._magnification)))
        self.vanillaWrapper().resizeFontItems(newItemSize, centerPoint=centerPoint)

    def scrollWheel_(self, event):
        if event.modifierFlags() & AppKit.NSEventModifierFlagOption:
            if event.phase() in {AppKit.NSEventPhaseBegan, AppKit.NSEventPhaseMayBegin}:
                self._originalItemSize = self.vanillaWrapper().itemSize
                self._magnification = 1.0
            centerPoint = self.convertPoint_fromView_(event.locationInWindow(), None)
            by = event.scrollingDeltaY() * 0.001  #
            self._magnification += by
            newItemSize = round(max(fontItemMinimumSize,
                                    min(fontItemMaximumSize, self._originalItemSize * self._magnification)))
            self.vanillaWrapper().resizeFontItems(newItemSize, centerPoint=centerPoint)
        else:
            super().scrollWheel_(event)

    _dragPosView = None

    @suppressAndLogException
    def draggingEntered_(self, draggingInfo):
        if any(fontItemIdentifier or sniffFontType(path) or path.is_dir()
               for path, fontNumber, fontItemIdentifier in self._iterateItemsFromDraggingInfo(draggingInfo)):
            self._weHaveValidDrag = True
            if self._dragPosView is None:
                self._dragPosView = AppKit.NSView.alloc().init()
                self._dragPosView.setWantsLayer_(True)
                self._dragPosView.setBackgroundColor_(controlAccentColor())
            index, frame = self._getDropInsertionIndexAndRect_(draggingInfo)
            self._dragPosView.setFrame_(frame)
            self.superview().addSubview_(self._dragPosView)
            return AppKit.NSDragOperationEvery
        else:
            self._weHaveValidDrag = False
            return AppKit.NSDragOperationNone

    @suppressAndLogException
    def draggingUpdated_(self, draggingInfo):
        if self._weHaveValidDrag:
            index, frame = self._getDropInsertionIndexAndRect_(draggingInfo)
            self._dragPosView.animator().setFrame_(frame)
            return AppKit.NSDragOperationEvery
        else:
            return AppKit.NSDragOperationNone

    @suppressAndLogException
    def draggingExited_(self, draggingInfo):
        if self._dragPosView is not None:
            self._dragPosView.removeFromSuperview()
            self._dragPosView = None

    @objc.signature(b"Z@:@")  # PyObjC bug?
    @suppressAndLogException
    def draggingEnded_(self, draggingInfo):
        if self._dragPosView is not None:
            self._dragPosView.removeFromSuperview()
            self._dragPosView = None

    def _getDropInsertionIndexAndRect_(self, draggingInfo):
        point = self.convertPoint_fromView_(draggingInfo.draggingLocation(), None)
        fontList = self.vanillaWrapper()
        numFontItems = fontList.getNumFontItems()
        itemSize = fontList.itemSize
        vertical = fontList.vertical
        frame = self.bounds()
        if numFontItems:
            index = round(point[1 - vertical] / itemSize)
            index = max(0, min(index, numFontItems))
        else:
            index = 0
        frame.origin[1 - vertical] = max(0, itemSize * index)
        dropBarSize = 2
        frame.size[1 - vertical] = dropBarSize

        frame.origin[vertical] -= frame.size[vertical] * 10
        frame.size[vertical] *= 20

        if not vertical and (not numFontItems or frame.origin[1 - vertical] >= self.frame().size[1 - vertical]):
            frame.origin[1 - vertical] = self.frame().size[1 - vertical] - dropBarSize
        if not vertical:
            index = numFontItems - index
        frame = self.superview().convertRect_fromView_(frame, self)
        return index, frame

    def prepareForDragOperation_(self, draggingInfo):
        return True

    @suppressAndLogException
    def performDragOperation_(self, draggingInfo):
        index, frame = self._getDropInsertionIndexAndRect_(draggingInfo)
        items = list(self._iterateItemsFromDraggingInfo(draggingInfo))
        if draggingInfo.draggingSource() is self:
            # Local drag, just reorder
            self.vanillaWrapper().moveFonts(items, index)
        else:
            self.vanillaWrapper().insertFonts(items, index)
        return True

    @staticmethod
    def _iterateItemsFromDraggingInfo(draggingInfo):
        for pbItem in draggingInfo.draggingPasteboard().pasteboardItems():
            urlString = pbItem.stringForType_(FGPasteboardTypeFileURL)
            url = AppKit.NSURL.alloc().initWithString_relativeToURL_(urlString, None)
            fontNumberString = pbItem.stringForType_(FGPasteboardTypeFontNumber)
            fontNumber = int(fontNumberString) if fontNumberString else None
            fontItemIdentifier = pbItem.stringForType_(FGPasteboardTypeFontItemIdentifier)
            yield pathlib.Path(url.path()), fontNumber, fontItemIdentifier

    # Undo/Redo

    @suppressAndLogException
    def undo_(self, sender):
        fontList = self.vanillaWrapper()
        undoChanges(fontList.projectProxy)

    @suppressAndLogException
    def redo_(self, sender):
        fontList = self.vanillaWrapper()
        redoChanges(fontList.projectProxy)

    @suppressAndLogException
    def validateMenuItem_(self, sender):
        if sender.action() == "undo:":
            fontList = self.vanillaWrapper()
            info = undoInfo(fontList.projectProxy)
            sender.setTitle_(_makeUndoTitle("Undo", info))
            return info is not None
        elif sender.action() == "redo:":
            fontList = self.vanillaWrapper()
            info = redoInfo(fontList.projectProxy)
            sender.setTitle_(_makeUndoTitle("Redo", info))
            return info is not None
        elif sender.action() == "delete:":
            fontList = self.vanillaWrapper()
            return bool(fontList.selection)
        else:
            return True

    @suppressAndLogException
    def delete_(self, sender):
        fontList = self.vanillaWrapper()
        fontList.removeSelectedFontItems()

    @suppressAndLogException
    def selectAll_(self, sender):
        fontList = self.vanillaWrapper()
        fontList.selectAll()


def _makeUndoTitle(mainTitle, info):
    title = [mainTitle]
    if info:
        undoName = info.get("title")
        if undoName:
            title.append(undoName)
    return " ".join(title)


arrowKeyDefs = {
    AppKit.NSUpArrowFunctionKey: (-1, 1),
    AppKit.NSDownArrowFunctionKey: (1, 1),
    AppKit.NSLeftArrowFunctionKey: (-1, 0),
    AppKit.NSRightArrowFunctionKey: (1, 0),
}


class FontList(Group):

    nsViewClass = FGFontListView

    def __init__(self, project, projectProxy, width, itemSize, vertical=False,
                 relativeFontSize=0.7, relativeHBaseline=0.25,
                 relativeVBaseline=0.5, relativeMargin=0.1,
                 showFontFileName=True, selectionChangedCallback=None,
                 glyphSelectionChangedCallback=None, arrowKeyCallback=None):
        super().__init__((0, 0, width, 900))
        self.project = None  # Dummy, so we can set up other attrs first
        self.relativeFontSize = relativeFontSize
        self.relativeHBaseline = relativeHBaseline
        self.relativeVBaseline = relativeVBaseline
        self.relativeMargin = relativeMargin
        self._selection = set()  # a set of indices
        self.vertical = int(vertical)  # 0, 1: it is also an index into (x, y) tuples
        self.itemSize = itemSize
        self.align = "left"
        self._selectionChangedCallback = selectionChangedCallback
        self._glyphSelectionChangedCallback = glyphSelectionChangedCallback
        self._arrowKeyCallback = arrowKeyCallback
        self._lastItemClicked = None
        self.project = project
        self.projectProxy = projectProxy
        self.setupFontItems()
        self.showFontFileName = showFontFileName

    def _glyphSelectionChanged(self):
        if self._glyphSelectionChangedCallback is not None:
            self._glyphSelectionChangedCallback(self)

    def setupFontItems(self):
        # clear all subviews
        for attr, value in list(self.__dict__.items()):
            if isinstance(value, VanillaBaseObject):
                delattr(self, attr)
        itemSize = self.itemSize
        if self.project.fonts:
            y = 0
            for index, fontItemInfo in enumerate(self.project.fonts):
                x = y = 0
                if self.vertical:
                    x = index * itemSize
                    w = itemSize
                    h = 0
                else:
                    y = index * itemSize
                    w = 0
                    h = itemSize
                fontItem = FontItem((x, y, w, h), fontItemInfo.fontKey, index, self.vertical,
                                    self.align, self.relativeFontSize, self.relativeHBaseline,
                                    self.relativeVBaseline, self.relativeMargin)
                setattr(self, fontItemInfo.identifier, fontItem)
                y += itemSize
        else:
            y = itemSize
            self.setupDropFontsPlaceholder()
        self.setPosSize((0, 0, self.width, y))

    def setupDropFontsPlaceholder(self):
        color = AppKit.NSColor.systemGrayColor()

        attrs = {
            AppKit.NSForegroundColorAttributeName: color,
            AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_(24),
        }
        header = AppKit.NSAttributedString.alloc().initWithString_attributes_(
            "Drop some fonts here!\n",
            attrs,
        )
        attrs[AppKit.NSFontAttributeName] = AppKit.NSFont.systemFontOfSize_(16)
        info = AppKit.NSAttributedString.alloc().initWithString_attributes_(
            supportedFormatsString,
            attrs,
        )
        text = AppKit.NSMutableAttributedString.alloc().init()
        text.appendAttributedString_(header)
        text.appendAttributedString_(info)

        self.dropFontsPlaceHolder = UnclickableTextBox(
            (10, 10, -10, -10), "", fontSize=22, textColor=color
        )
        self.dropFontsPlaceHolder._nsObject.setAttributedStringValue_(text)

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

    def showFontFileName(self):
        for fontItem in self.iterFontItems():
            fontItem.fileNameLabel.show(self.showFontFileName)

    showFontFileName = hookedProperty(showFontFileName, default=True)

    def iterFontItems(self):
        if self.project is None:
            return
        for fontItemInfo in self.project.fonts:
            yield self.getFontItem(fontItemInfo.identifier)

    def iterFontItemInfoAndItems(self):
        if self.project is None:
            return
        for fontItemInfo in self.project.fonts:
            yield fontItemInfo, self.getFontItem(fontItemInfo.identifier)

    @hookedProperty
    def vertical(self):
        # Note that we heavily depend on hookedProperty's property that
        # the hook is only called when the value is different than before.
        vertical = self.vertical
        pos = [0, 0]
        for fontItem in self.iterFontItems():
            fontItem.vertical = vertical
            fontItem.fileNameLabel.setPosSize(getFileNameLabelPosSize(vertical))
            fontItem.fileNameLabel.rotate([-90, 90][vertical])
            fontItem.progressSpinner.setPosSize(getProgressSpinnerPosSize(vertical))
            x, y, w, h = fontItem.getPosSize()
            w, h = h, w
            fontItem.setPosSize((*pos, w, h))
            pos[1 - vertical] += self.itemSize
        x, y, w, h = self.getPosSize()
        w, h = h, w
        self.setPosSize((x, y, w, h))
        self._nsObject.setNeedsDisplay_(True)

    @hookedProperty
    @asyncTaskAutoCancel
    async def relativeFontSize(self):
        for fontItem in self.iterFontItems():
            fontItem.relativeSize = self.relativeFontSize

    @hookedProperty
    @asyncTaskAutoCancel
    async def relativeHBaseline(self):
        for fontItem in self.iterFontItems():
            fontItem.relativeHBaseline = self.relativeHBaseline

    @hookedProperty
    @asyncTaskAutoCancel
    async def relativeVBaseline(self):
        for fontItem in self.iterFontItems():
            fontItem.relativeVBaseline = self.relativeVBaseline

    @hookedProperty
    @asyncTaskAutoCancel
    async def relativeMargin(self):
        for fontItem in self.iterFontItems():
            fontItem.relativeMargin = self.relativeMargin

    @suppressAndLogException
    def resizeFontItems(self, itemSize, centerPoint=None):
        if not self.project.fonts:
            return
        scaleFactor = itemSize / self.itemSize
        self.itemSize = itemSize
        pos = [0, 0]
        for fontItem in self.iterFontItems():
            x, y, *wh = fontItem.getPosSize()
            wh[1 - self.vertical] = itemSize
            fontItem.setPosSize((*pos, *wh))
            pos[1 - self.vertical] += itemSize

        clipView = self._nsObject.superview()
        x, y, w, h = self.getPosSize()
        (cx, cy), (cw, ch) = clipView.bounds()
        if centerPoint is not None:
            # centerPoint is in doc view coordinates (self), convert to clipView
            centerX, centerY = clipView.convertPoint_fromView_(centerPoint, self._nsObject)
            # rcx and rcy are relative to the clip views origin
            rcx = centerX - cx
            rcy = ch - (centerY - cy)
        else:
            # rcx and rcy are relative to the clip views origin
            rcx = cw / 2
            rcy = ch / 2
        cx += rcx
        cy -= rcy
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
        cx -= rcx
        cy += rcy
        clipBounds = clipView.bounds()
        clipBounds.origin = (cx, cy)
        clipView.setBounds_(clipBounds)

    @suppressAndLogException
    def insertFonts(self, items, index):
        addedItems = []
        self.project.fontSelection = self.selection
        pathsExternal = [fontPath for fontPath, fontNumber, fontItemIdentifier in items
                         if fontNumber is None]
        pathsAndFontNumbers = [(fontPath, fontNumber) for fontPath, fontNumber, fontItemIdentifier in items
                               if fontNumber is not None]
        items = sortedFontPathsAndNumbers(pathsExternal, defaultSortSpec) + pathsAndFontNumbers
        fontsProxy = self.projectProxy.fonts
        with recordChanges(fontsProxy, title="Insert Fonts"):
            for fontPath, fontNumber in items:
                fontItemInfo = self.project.newFontItemInfo(fontPath, fontNumber)
                fontsProxy.insert(index, fontItemInfo)
                addedItems.append(fontItemInfo.identifier)
                index += 1
            self.projectProxy.fontSelection = self.selection
        self.scrollSelectionToVisible(addedItems)

    @suppressAndLogException
    def moveFonts(self, items, index):
        allItems = [fontItemInfo.identifier for fontItemInfo in self.project.fonts]
        movingItems = [fontItemIdentifier for fontPath, fontNumber, fontItemIdentifier in items]
        movingItemsSet = set(movingItems)
        movedItems = []
        for i, identifier in enumerate(allItems):
            if i == index:
                movedItems.extend(movingItems)
            if identifier not in movingItemsSet:
                movedItems.append(identifier)
        if index >= len(allItems):
            movedItems.extend(movingItems)
        assert len(movedItems) == len(allItems)
        if allItems == movedItems:
            # Nothing moved
            return

        self.project.fontSelection = self.selection
        with recordChanges(self.projectProxy, title="Reorder Fonts"):
            self.projectProxy.fontSelection = self.selection
            itemDict = {item.identifier: item for item in self.project.fonts}
            fontsProxy = self.projectProxy.fonts
            for i, itemIdentifier in enumerate(movedItems):
                fontsProxy[i] = itemDict[itemIdentifier]
            self.selection = set(movingItems)
            self.projectProxy.fontSelection = self.selection

    def removeSelectedFontItems(self):
        indicesToDelete = sorted(self.selectionIndices, reverse=True)
        self.ensureFirstResponder()
        self.project.fontSelection = self.selection
        with recordChanges(self.projectProxy, title="Remove Fonts"):
            self.projectProxy.fontSelection = self.selection
            fontsProxy = self.projectProxy.fonts
            for index in indicesToDelete:
                del fontsProxy[index]
            self.selection = set()
            self.projectProxy.fontSelection = self.selection

    def ensureFirstResponder(self):
        # If originally one of th font list items is first responder
        # but gets deleted, the font list itself should becode first
        # responder.
        self._nsObject.window().makeFirstResponder_(self._nsObject)

    def refitFontItems(self):
        if hasattr(self, "dropFontsPlaceHolder"):
            del self.dropFontsPlaceHolder
        itemSize = self.itemSize
        fontItemsNeedingTextUpdate = []
        for index, fontItemInfo in enumerate(self.project.fonts):
            fontItem = getattr(self, fontItemInfo.identifier, None)
            if fontItem is None:
                x, y, w, h = self.getPosSize()
                if self.vertical:
                    x = index * itemSize
                    w = itemSize
                    h = 0
                else:
                    y = index * itemSize
                    w = 0
                    h = itemSize
                fontItem = FontItem((x, y, w, h), fontItemInfo.fontKey, index, self.vertical,
                                    self.align, self.relativeFontSize, self.relativeHBaseline,
                                    self.relativeVBaseline, self.relativeMargin)
                setattr(self, fontItemInfo.identifier, fontItem)
                if fontItemInfo.font is not None:
                    # Font is already loaded, but the text needs to be updated.
                    fontItemsNeedingTextUpdate.append((fontItemInfo, fontItem))
            else:
                fontItem.fontListIndex = index
                x, y, w, h = fontItem.getPosSize()
                if self.vertical:
                    x = index * itemSize
                else:
                    y = index * itemSize
                fontItem.setPosSize((x, y, w, h))
        x, y, w, h = self.getPosSize()
        if self.vertical:
            w = len(self.project.fonts) * itemSize
        else:
            h = len(self.project.fonts) * itemSize
        self.setPosSize((x, y, w, h))
        return fontItemsNeedingTextUpdate

    def purgeFontItems(self):
        usedIdentifiers = {fii.identifier for fii in self.project.fonts}
        staleIdentifiers = []
        for attr, value in self.__dict__.items():
            if attr not in usedIdentifiers and isinstance(value, VanillaBaseObject):
                staleIdentifiers.append(attr)
        for attr in staleIdentifiers:
            delattr(self, attr)

    @property
    def selection(self):
        return self._selection

    @selection.setter
    def selection(self, newSelection):
        diffSelection = self._selection ^ newSelection
        self._selection = newSelection
        for identifier in diffSelection:
            try:
                fontItem = self.getFontItem(identifier)
            except AttributeError:
                self._selection.discard(identifier)
            else:
                fontItem.selected = not fontItem.selected
        if self._selectionChangedCallback is not None:
            self._selectionChangedCallback(self)

    @property
    def selectionIndices(self):
        return {index for index, fii in enumerate(self.project.fonts) if fii.identifier in self._selection}

    @selectionIndices.setter
    def selectionIndices(self, newSelection):
        self.selection = {self.project.fonts[index].identifier for index in newSelection}

    def selectAll(self):
        self.selection = {fii.identifier for fii in self.project.fonts}

    def getFontItem(self, fontItemIdentifier):
        return getattr(self, fontItemIdentifier)

    def getFontItemByIndex(self, index):
        return getattr(self, self.project.fonts[index].identifier)

    def getNumFontItems(self):
        return len(self.project.fonts)

    def getSingleSelectedItem(self):
        if len(self.project.fonts) == 1:
            return self.getFontItemByIndex(0)
        elif len(self.selection) == 1:
            identifier = list(self.selection)[0]
            try:
                return self.getFontItem(identifier)
            except AttributeError:
                return None  # item got deleted, it's fine
        else:
            return None

    def _getSelectionRect(self, selection):
        selRect = None
        for identifier in selection:
            fontItem = self.getFontItem(identifier)
            if selRect is None:
                selRect = fontItem._nsObject.frame()
            else:
                selRect = AppKit.NSUnionRect(selRect, fontItem._nsObject.frame())
        return selRect

    def scrollSelectionToVisible(self, selection=None):
        if selection is None:
            selection = self._selection
        selRect = self._getSelectionRect(selection)
        if selRect is not None:
            self._nsObject.scrollRectToVisible_(selRect)

    def scrollGlyphSelectionToVisible(self):
        if self.selection:
            fontItems = (self.getFontItem(identifier) for identifier in self.selection)
        else:
            fontItems = (self.getFontItem(fiInfo.identifier) for fiInfo in self.project.fonts)
        rects = []
        for fontItem in fontItems:
            view = fontItem.glyphLineView._nsObject
            x, y = fontItem._nsObject.frame().origin
            selRect = view.getSelectionRect()
            if selRect is not None:
                rects.append(AppKit.NSOffsetRect(selRect, x, y))
        if rects:
            selRect = rects[0]
            for rect in rects[1:]:
                selRect = AppKit.NSUnionRect(selRect, rect)
            self._nsObject.scrollRectToVisible_(selRect)

    @suppressAndLogException
    def mouseDown(self, event):
        pass

    @suppressAndLogException
    def mouseDragged(self, event):
        clickedIdentifier = self.project.fonts[self._lastItemClicked].identifier
        if clickedIdentifier not in self.selection:
            self.selection = {clickedIdentifier}
        selectedIndices = {i for i, fii in enumerate(self.project.fonts)
                           if fii.identifier in self.selection}
        items = [self.project.fonts[i] for i in sorted(selectedIndices)]
        dragItems = []
        xOffset = yOffset = 0
        for item in items:
            pbItem = AppKit.NSPasteboardItem.alloc().init()
            fontPath, fontNumber = item.fontKey
            fileURL = AppKit.NSURL.fileURLWithPath_(str(fontPath))
            pbItem.setString_forType_(fileURL.absoluteString(), FGPasteboardTypeFileURL)
            pbItem.setString_forType_(str(fontNumber), FGPasteboardTypeFontNumber)
            pbItem.setString_forType_(item.identifier, FGPasteboardTypeFontItemIdentifier)
            dragItem = AppKit.NSDraggingItem.alloc().initWithPasteboardWriter_(pbItem)
            point = self._nsObject.convertPoint_fromView_(event.locationInWindow(), None)
            dragItem.setDraggingFrame_(((point.x + xOffset, point.y - yOffset), (10, 10)))
            if self.vertical:
                xOffset += 50
            else:
                yOffset += 50

            def imageComponentsProvider(identifier=item.identifier):
                fontItem = self.getFontItem(identifier)
                image = fontItem._nsObject.imageRepresentation()
                imageComponent = AppKit.NSDraggingImageComponent.draggingImageComponentWithKey_(
                        AppKit.NSDraggingImageComponentIconKey)
                imageComponent.setContents_(image)
                imageComponent.setFrame_(((0, -image.size().height), image.size()))
                return [imageComponent]

            dragItem.setImageComponentsProvider_(imageComponentsProvider)
            dragItems.append(dragItem)

        self._nsObject.beginDraggingSessionWithItems_event_source_(dragItems, event, self._nsObject)

    @suppressAndLogException
    def mouseUp(self, event):
        glyphSelectionChanged = False
        index = self._lastItemClicked  # TODO: This needs to be permanent and get a better API
        self._lastItemClicked = None
        if index is not None:
            fontItem = self.getFontItemByIndex(index)
            glyphSelectionChanged = bool(fontItem.popDiffSelection())
            clickedSelection = {self.project.fonts[index].identifier}
        else:
            for fontItem in self.iterFontItems():
                fontItem.selection = set()
            glyphSelectionChanged = True
            clickedSelection = set()

        if clickedSelection and event.modifierFlags() & AppKit.NSEventModifierFlagCommand:
            newSelection = self._selection ^ clickedSelection
        elif clickedSelection and event.modifierFlags() & AppKit.NSEventModifierFlagShift:
            if not self._selection:
                newSelection = clickedSelection
            else:
                selIndices = [index for index, fontItemInfo in enumerate(self.project.fonts)
                              if fontItemInfo.identifier in self._selection]
                minSel = min(selIndices)
                maxSel = max(selIndices)
                if index < minSel:
                    selIndices = range(index, maxSel + 1)
                elif index > maxSel:
                    selIndices = range(minSel, index + 1)
                else:
                    selIndices = range(minSel, maxSel + 1)
                newSelection = {self.project.fonts[i].identifier for i in selIndices}
        elif index in self._selection:
            newSelection = None
        else:
            newSelection = clickedSelection
        if newSelection is not None:
            self.selection = newSelection
            if clickedSelection:
                self.scrollSelectionToVisible(clickedSelection)
        if glyphSelectionChanged:
            self._glyphSelectionChanged()

    @suppressAndLogException
    def keyDown(self, event):
        chars = event.characters()
        if chars in arrowKeyDefs:
            direction, vertical = arrowKeyDefs[chars]
            if vertical == self.vertical:
                if self._arrowKeyCallback is not None:
                    self._arrowKeyCallback(self, event)
                return True

            numFontItems = len(self.project.fonts)
            if not self.selectionIndices:
                if direction == 1:
                    self.selectionIndices = {0}
                else:
                    self.selectionIndices = {numFontItems - 1}
            else:
                if direction == 1:
                    index = min(numFontItems - 1, max(self.selectionIndices) + 1)
                else:
                    index = max(0, min(self.selectionIndices) - 1)
                if event.modifierFlags() & AppKit.NSEventModifierFlagShift:
                    self.selectionIndices = self.selectionIndices | {index}
                else:
                    self.selectionIndices = {index}
            self.scrollSelectionToVisible()
            return True
        return False


def _scheduleRedraw(self):
    self.setNeedsDisplay_(True)


class FGFontItemView(AppKit.NSView):

    selected = hookedProperty(_scheduleRedraw, default=False)
    hasWarningOrError = hookedProperty(_scheduleRedraw, default=False)

    def init(self):
        self = super().init()
        self.selected = False
        return self

    @cachedProperty
    def errorOverlayColor(self):
        im = AppKit.NSImage.imageNamed_("errorPatternImage")
        assert im is not None
        return AppKit.NSColor.colorWithPatternImage_(im)

    def drawRect_(self, rect):
        if not self.selected:
            backgroundColor = AppKit.NSColor.textBackgroundColor()
        else:
            backgroundColor = AppKit.NSColor.textBackgroundColor().blendedColorWithFraction_ofColor_(
                0.5, AppKit.NSColor.selectedTextBackgroundColor())
        backgroundColor.set()
        AppKit.NSRectFill(rect)
        if self.hasWarningOrError:
            self.errorOverlayColor.set()
            AppKit.NSRectFillUsingOperation(rect, AppKit.NSCompositeSourceOver)

    @suppressAndLogException
    def revealInFinder_(self, sender):
        fontPath = os.fspath(self.vanillaWrapper().fontPath)
        workspace = AppKit.NSWorkspace.sharedWorkspace()
        workspace.selectFile_inFileViewerRootedAtPath_(fontPath, "")

    @suppressAndLogException
    def reloadFont_(self, sender):
        # Factorisation is suboptimal don't @ me
        fontItem = self.vanillaWrapper()
        fontList = self.superview().vanillaWrapper()
        fontItemInfo = fontList.project.fonts[fontItem.fontListIndex]
        fontItemInfo.unload()
        self.window().windowController().loadFonts()

    @suppressAndLogException
    def clearCompileOutput_(self, sender):
        fontItem = self.vanillaWrapper()
        fontItem.clearCompileOutput()

    def validateMenuItem_(self, sender):
        if sender.action() == "clearCompileOutput:":
            fontItem = self.vanillaWrapper()
            return bool(fontItem.getCompileOutput())
        return True

    def menuForEvent_(self, event):
        menu = AppKit.NSMenu.alloc().initWithTitle_("Contextual Menu")
        items = [
            ("Reveal font file in Finder", "revealInFinder:"),
            ("Reload font", "reloadFont:"),
            ("Clear error", "clearCompileOutput:"),
        ]
        for i, (title, action) in enumerate(items):
            menu.insertItemWithTitle_action_keyEquivalent_atIndex_(title, action, "", i)
        return menu

    @suppressAndLogException
    def mouseDown_(self, event):
        if event.modifierFlags() & AppKit.NSEventModifierFlagControl:
            menu = self.menuForEvent_(event)
            AppKit.NSMenu.popUpContextMenu_withEvent_forView_(menu, event, self)
        else:
            super().mouseDown_(event)

    @suppressAndLogException
    def imageRepresentation(self):
        wasSelected = self.selected
        self.selected = False
        bitmapRep = self.bitmapImageRepForCachingDisplayInRect_(self.bounds())
        self.cacheDisplayInRect_toBitmapImageRep_(self.bounds(), bitmapRep)
        image = AppKit.NSImage.alloc().init()
        image.addRepresentation_(bitmapRep)
        bitmapRep.setSize_(self.bounds().size)
        self.selected = wasSelected
        return image


class FontItem(Group):

    nsViewClass = FGFontItemView
    selected = delegateProperty("_nsObject")
    hasWarningOrError = delegateProperty("_nsObject")
    vertical = delegateProperty("glyphLineView")
    relativeSize = delegateProperty("glyphLineView")
    relativeHBaseline = delegateProperty("glyphLineView")
    relativeVBaseline = delegateProperty("glyphLineView")
    relativeMargin = delegateProperty("glyphLineView")

    def __init__(self, posSize, fontKey, fontListIndex, vertical, align,
                 relativeSize, relativeHBaseline, relativeVBaseline, relativeMargin):
        super().__init__(posSize)
        # self._nsObject.setWantsLayer_(True)
        # self._nsObject.setCanDrawSubviewsIntoLayer_(True)
        self.fontListIndex = fontListIndex
        self.fileNameLabel = UnclickableTextBox(getFileNameLabelPosSize(vertical), "", sizeStyle="small",
                                                textColor=AppKit.NSColor.systemGrayColor())
        self.glyphLineView = GlyphLine((0, 0, 0, 0))
        self.vertical = vertical
        self.relativeSize = relativeSize
        self.relativeHBaseline = relativeHBaseline
        self.relativeVBaseline = relativeVBaseline
        self.relativeMargin = relativeMargin
        self.align = align
        self.selected = False
        if vertical:
            self.fileNameLabel.rotate(90)
        self.progressSpinner = ProgressSpinner(getProgressSpinnerPosSize(vertical))
        self.setFontKey(fontKey)
        self.compileOutput = io.StringIO()
        self._auxillaryOutput = [None]  # Avoid vanilla setattr magic
        self._isLoadingCounter = 0

    def setIsLoading(self, isLoading):
        if isLoading:
            if not self._isLoadingCounter:
                self.progressSpinner.start()
            self._isLoadingCounter += 1
        else:
            self._isLoadingCounter -= 1
            if not self._isLoadingCounter:
                self.progressSpinner.stop()

    def setFontKey(self, fontKey, nameInCollection=None):
        fontPath, fontNumber = fontKey
        fileNameLabel = f"{fontPath.name}"
        if nameInCollection:
            fileNameLabel += f"#{nameInCollection}"
        elif fontNumber or fontPath.suffix.lower() in {".ttc", ".otc"}:
            fileNameLabel += f"#{fontNumber}"
        self.fileNameLabel.set(fileNameLabel, tooltip=str(fontPath))
        self.fontPath = fontPath

    def setAuxillaryOutput(self, outputView):
        self._auxillaryOutput[0] = outputView

    def writeCompileOutput(self, text):
        self.compileOutput.write(text)
        if self._auxillaryOutput[0] is not None:
            self._auxillaryOutput[0].write(text)
        self.hasWarningOrError = True

    def getCompileOutput(self):
        return self.compileOutput.getvalue()

    def clearCompileOutput(self):
        self.compileOutput.seek(0)
        self.compileOutput.truncate()
        if self._auxillaryOutput[0] is not None:
            self._auxillaryOutput[0].clear()
        self.hasWarningOrError = False

    @property
    def glyphs(self):
        return self.glyphLineView._nsObject._glyphs

    @glyphs.setter
    def glyphs(self, glyphs):
        self.glyphLineView._nsObject.glyphs = glyphs

    @property
    def selection(self):
        return self.glyphLineView._nsObject.selection

    @selection.setter
    def selection(self, newSelection):
        self.glyphLineView._nsObject.selection = newSelection

    def popDiffSelection(self):
        return self.glyphLineView._nsObject.popDiffSelection()

    @property
    def minimumExtent(self):
        return self.glyphLineView._nsObject.minimumExtent

    @property
    def align(self):
        return self.glyphLineView._nsObject.align

    @align.setter
    def align(self, value):
        if self.vertical:
            mapping = dict(top="left", center="center", bottom="right")
            value = mapping.get(value, value)
        self.fileNameLabel.align = value
        self.glyphLineView._nsObject.align = value


def getFileNameLabelPosSize(vertical):
    if vertical:
        return (2, 10, 17, -10)
    else:
        return (10, 0, -10, 17)


def getProgressSpinnerPosSize(vertical):
    if vertical:
        return (20, 10, 25, 25)
    else:
        return (10, 20, 25, 25)


class FGGlyphLineView(AppKit.NSView):

    align = hookedProperty(_scheduleRedraw, default="left")
    relativeSize = hookedProperty(_scheduleRedraw, default=0.7)
    relativeHBaseline = hookedProperty(_scheduleRedraw, default=0.25)
    relativeVBaseline = hookedProperty(_scheduleRedraw, default=0.5)
    relativeMargin = hookedProperty(_scheduleRedraw, default=0.1)

    def init(self):
        self = super().init()
        self.vertical = 0  # 0, 1: it will also be an index into (x, y) tuples
        self._glyphs = None
        self._rectTree = None
        self._selection = set()
        self._hoveredGlyphIndex = None
        self._lastDiffSelection = None
        self._lastAppearanceName = None
        self._glyphsColorPalette = None
        self._cachedColorPalettes = {}

        trackingArea = AppKit.NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            self.bounds(),
            AppKit.NSTrackingActiveInKeyWindow | AppKit.NSTrackingMouseMoved |
            AppKit.NSTrackingMouseEnteredAndExited | AppKit.NSTrackingInVisibleRect,
            self, None)
        self.addTrackingArea_(trackingArea)

        return self

    def acceptsFirstResponder(self):
        return True

    def acceptsFirstMouse(self):
        return True

    def becomeFirstResponder(self):
        # Defer to our FGFontListView
        fontListView = self.superview().superview()
        assert isinstance(fontListView, FGFontListView)
        return fontListView.becomeFirstResponder()

    @property
    def selection(self):
        return self._selection

    @selection.setter
    def selection(self, newSelection):
        diffSelection = self._selection ^ newSelection
        self._selection = newSelection
        for index in diffSelection:
            bounds = self.getGlyphBounds_(index)
            if bounds is not None:
                self.setNeedsDisplayInRect_(bounds)
        self._lastDiffSelection = diffSelection

    @property
    def hoveredGlyphIndex(self):
        return self._hoveredGlyphIndex

    @hoveredGlyphIndex.setter
    def hoveredGlyphIndex(self, index):
        hoveredGlyphIndex = self._hoveredGlyphIndex
        if index == hoveredGlyphIndex:
            return
        prevBounds = self.getGlyphBounds_(hoveredGlyphIndex)
        newBounds = self.getGlyphBounds_(index)
        if prevBounds is None:
            bounds = newBounds
        elif newBounds is None:
            bounds = prevBounds
        else:
            bounds = AppKit.NSUnionRect(prevBounds, newBounds)
        self._hoveredGlyphIndex = index
        if bounds is not None:
            self.setNeedsDisplayInRect_(bounds)

    def getGlyphBounds_(self, index):
        if index is None or index >= len(self._glyphs):
            return None
        bounds = self._glyphs[index].bounds
        if bounds is None:
            return None
        dx, dy = self.origin
        scaleFactor = self.scaleFactor
        bounds = offsetRect(scaleRect(bounds, scaleFactor, scaleFactor), dx, dy)
        return nsRectFromRect(bounds)

    def getSelectionRect(self):
        """This methods returns an NSRect suitable for scrollRectToVisible_.
        It uses the "advance box" of selected glyphs, not the bounding box.
        """
        if not self._glyphs:
            return None
        scaleFactor = self.scaleFactor
        origin = self.origin
        extent = self.frame().size[1 - self.vertical]
        bounds = None
        for glyphIndex in self.selection:
            gi = self.glyphs[glyphIndex]
            pos = gi.pos[self.vertical] * scaleFactor + origin[self.vertical]
            adv = [gi.ax, gi.ay][self.vertical] * scaleFactor
            delta = [gi.dx, gi.dy][self.vertical] * scaleFactor
            if self.vertical:
                box = (0, pos - delta + adv, extent, pos - delta)
            else:
                box = (pos + delta, 0, pos + delta + adv, extent)
            if bounds is None:
                bounds = box
            else:
                bounds = unionRect(bounds, box)

        if bounds is None:
            return None
        dx, dy = self.origin
        return nsRectFromRect(bounds)

    def popDiffSelection(self):
        diffSelection = self._lastDiffSelection
        self._lastDiffSelection = None
        return diffSelection

    @property
    def glyphs(self):
        return self._glyphs

    @glyphs.setter
    def glyphs(self, glyphs):
        self._glyphs = glyphs
        rectIndexList = [(gi.bounds, index) for index, gi in enumerate(glyphs) if gi.bounds is not None]
        self._rectTree = RectTree.fromSeq(rectIndexList)
        self._selection = set()
        self._hoveredGlyphIndex = None  # no need to trigger smart redraw calculation
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
        return self.relativeSize * itemSize / self._glyphs.unitsPerEm

    @property
    def margin(self):
        itemSize = self.frame().size[1 - self.vertical]
        return self.relativeMargin * itemSize

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
            return pos, self.relativeHBaseline * itemSize
        else:
            return self.relativeVBaseline * itemSize, itemExtent - pos

    def getColors(self):
        appearanceName = AppKit.NSAppearance.currentAppearance().name()
        if appearanceName != self._lastAppearanceName:
            self._lastAppearanceName = appearanceName
            foregroundColor = AppKit.NSColor.textColor()
            selectedColor = foregroundColor.blendedColorWithFraction_ofColor_(
                0.9, AppKit.NSColor.systemRedColor())
            selectedSpaceColor = selectedColor.colorWithAlphaComponent_(0.2)
            hoverColor = AppKit.NSColor.systemBlueColor()
            hoverSelectedColor = hoverColor.blendedColorWithFraction_ofColor_(
                0.5, selectedColor)
            hoverSpaceColor = hoverColor.colorWithAlphaComponent_(0.2)
            hoverSelectedSpaceColor = hoverSelectedColor.colorWithAlphaComponent_(0.2)

            colors = SimpleNamespace(
                foregroundColor=rgbaFromNSColor(foregroundColor),
                selectedColor=rgbaFromNSColor(selectedColor),
                selectedSpaceColor=rgbaFromNSColor(selectedSpaceColor),
                hoverColor=rgbaFromNSColor(hoverColor),
                hoverSelectedColor=rgbaFromNSColor(hoverSelectedColor),
                hoverSpaceColor=rgbaFromNSColor(hoverSpaceColor),
                hoverSelectedSpaceColor=rgbaFromNSColor(hoverSelectedSpaceColor),
            )
            self._colors = colors
        return self._colors

    @objc.python_method
    def getColorPalette(self, blendColor):
        if self._glyphsColorPalette != self._glyphs.colorPalette:
            self._glyphsColorPalette = self._glyphs.colorPalette
            self._cachedColorPalettes = {}
        if not self._glyphsColorPalette:
            return []
        mainPalette = self._cachedColorPalettes.get(None)
        if mainPalette is None:
            mainPalette = self._glyphs.colorPalette
            self._cachedColorPalettes[None] = mainPalette
        blendedPalette = self._cachedColorPalettes.get(blendColor)
        if blendedPalette is None:
            blendedPalette = [
                blendRGBA(0.5, color, blendColor)
                for color in mainPalette
            ]
            self._cachedColorPalettes[blendColor] = blendedPalette
        return blendedPalette

    @suppressAndLogException
    def drawRect_(self, rect):
        if not self._glyphs:
            return

        colors = self.getColors()
        colorTable = {
            # (empty, selected, hovered)
            (0, 0, 0): colors.foregroundColor,
            (0, 0, 1): colors.hoverColor,
            (0, 1, 0): colors.selectedColor,
            (0, 1, 1): colors.hoverSelectedColor,
            (1, 0, 0): None,
            (1, 0, 1): colors.hoverSpaceColor,
            (1, 1, 0): colors.selectedSpaceColor,
            (1, 1, 1): colors.hoverSelectedSpaceColor,
        }

        selection = self._selection
        hoveredGlyphIndex = self._hoveredGlyphIndex

        dx, dy = self.origin

        invScale = 1 / self.scaleFactor
        rect = rectFromNSRect(rect)
        rect = scaleRect(offsetRect(rect, -dx, -dy), invScale, invScale)

        translate(dx, dy)
        scale(self.scaleFactor)

        lastPosX = lastPosY = 0
        for index in self._rectTree.iterIntersections(rect):
            gi = self._glyphs[index]
            selected = index in selection
            hovered = index == hoveredGlyphIndex
            empty = gi.glyphDrawing.bounds is None
            posX, posY = gi.pos
            translate(posX - lastPosX, posY - lastPosY)
            lastPosX, lastPosY = posX, posY
            color = colorTable[empty, selected, hovered]
            if color is None:
                continue
            if empty:
                nsColorFromRGBA(color).set()
                AppKit.NSRectFillUsingOperation(nsRectFromRect(offsetRect(gi.bounds, -posX, -posY)),
                                                AppKit.NSCompositeSourceOver)
            else:
                blendColor = None if color == colors.foregroundColor else color
                try:
                    gi.glyphDrawing.draw(self.getColorPalette(blendColor), color)
                except Exception as e:
                    logging.error(e)

    def mouseMoved_(self, event):
        point = self.convertPoint_fromView_(event.locationInWindow(), None)
        self.hoveredGlyphIndex = self.findGlyph_(point)

    def mouseEntered_(self, event):
        pass

    def mouseExited_(self, event):
        self.hoveredGlyphIndex = None

    @suppressAndLogException
    def mouseDown_(self, event):
        if event.modifierFlags() & AppKit.NSEventModifierFlagControl:
            # The event will be handled by our superview
            super().mouseDown_(event)
            return
        self.mouseDownLocation = self.convertPoint_fromView_(event.locationInWindow(), None)
        self.mouseDownGlyphIndex = self.findGlyph_(self.mouseDownLocation)

        # tell our parent we've been clicked on
        fontListIndex = self.superview().vanillaWrapper().fontListIndex
        fontList = self.superview().superview().vanillaWrapper()
        fontList._lastItemClicked = fontListIndex

        super().mouseDown_(event)

    def mouseDragged_(self, event):
        if (event.modifierFlags() & AppKit.NSEventModifierFlagCommand or
                event.modifierFlags() & AppKit.NSEventModifierFlagShift):
            return
        mx, my = self.mouseDownLocation
        x, y = self.convertPoint_fromView_(event.locationInWindow(), None)
        if math.hypot(x - mx, y - my) > 15:
            # Only do a drag beyond a minimum dragged distance
            self.mouseDownGlyphIndex = None
            super().mouseDragged_(event)

    def mouseUp_(self, event):
        index = self.mouseDownGlyphIndex
        if index is not None:
            if not (event.modifierFlags() & AppKit.NSEventModifierFlagCommand or
                    event.modifierFlags() & AppKit.NSEventModifierFlagShift):
                if index is None:
                    newSelection = set()
                elif index in self.selection:
                    newSelection = self.selection
                else:
                    newSelection = {index}
                self.selection = newSelection
        else:
            self.selection = set()

        super().mouseUp_(event)

    def findGlyph_(self, point):
        if self._rectTree is None:
            return None

        x, y = point
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
                if gi.glyphDrawing.pointInside((x - posX, y - posY)):
                    break
            else:
                index = indices[-1]
        return index


class GlyphLine(Group):
    nsViewClass = FGGlyphLineView
    selected = delegateProperty("_nsObject")
    vertical = delegateProperty("_nsObject")
    relativeSize = delegateProperty("_nsObject")
    relativeHBaseline = delegateProperty("_nsObject")
    relativeVBaseline = delegateProperty("_nsObject")
    relativeMargin = delegateProperty("_nsObject")


class FGUnclickableTextField(AppKit.NSTextField):

    def hitTest_(self, point):
        return None


class UnclickableTextBox(TextBox):

    """This TextBox sublass is transparent for clicks."""

    nsTextFieldClass = FGUnclickableTextField

    def __init__(self, posSize, text="", fontSize=None, textColor=None, **kwargs):
        attrs = {}
        if textColor is not None:
            attrs[AppKit.NSForegroundColorAttributeName] = textColor
        if fontSize is not None:
            attrs[AppKit.NSFontAttributeName] = AppKit.NSFont.systemFontOfSize_(fontSize)
        self.textAttributes = attrs
        text = self.makeAttrString(text)
        super().__init__(posSize, text, **kwargs)
        cell = self._nsObject.cell()
        cell.setLineBreakMode_(AppKit.NSLineBreakByTruncatingMiddle)

    def makeAttrString(self, text):
        if text and self.textAttributes:
            text = AppKit.NSAttributedString.alloc().initWithString_attributes_(text, self.textAttributes)
        return text

    def set(self, value, tooltip=None):
        super().set(self.makeAttrString(value))
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
        parStyle = AppKit.NSMutableParagraphStyle.alloc().init()
        parStyle.setAlignment_(nsAlignment)
        self.textAttributes[AppKit.NSParagraphStyleAttributeName] = parStyle
        self.set(self.get())


def controlAccentColor():
    if hasattr(AppKit.NSColor, "controlAccentColor"):
        return AppKit.NSColor.controlAccentColor()
    else:
        return AppKit.NSColor.systemBlueColor()
