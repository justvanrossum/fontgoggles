import re
import unicodedata2 as unicodedata
import AppKit
from vanilla import Button, EditText, FloatingWindow, List, TextBox, HorizontalLine
from ..misc.unicodeNameList import findPrefix
from .misc import makeTextCell


_unicodePat = re.compile(r"(([u]\+?)|(0x)|uni)?([0-9a-f]+)$", re.IGNORECASE)


class UnicodePicker(AppKit.NSWindowController):

    def __new__(cls):
        return cls.alloc().init()

    def __init__(self):
        self.searchResults = []
        self.selectedChars = ""

        self.w = FloatingWindow((300, 400), "Unicode Picker", minSize=(250, 300),
                                autosaveName="UnicodePicker")
        y = 8
        self.w.searchField = EditText((10, y, -10, 25),
                                      placeholder="Search Unicode name or value",
                                      callback=self.searchTextChanged_)

        y = 40
        columnDescriptions = [
            dict(title="char", width=40,
                 cell=makeTextCell(align="center", font=AppKit.NSFont.systemFontOfSize_(14))),
            dict(title="unicode", width=63, cell=makeTextCell(align="right")),
            dict(title="name"),
        ]
        self.w.unicodeList = List((0, y, 0, -100), [], columnDescriptions=columnDescriptions,
                                  rowHeight=18,
                                  selectionCallback=self.listSelectionChanged_,
                                  doubleClickCallback=self.listDoubleClickCallback_)
        self.w.unicodeList._nsObject.setBorderType_(AppKit.NSNoBorder)

        y = -100
        self.w.divider = HorizontalLine((0, y, 0, 1))
        y += 5
        self.w.unicodeText = TextBox((20, y, -10, 55), "")
        self.w.unicodeText._nsObject.cell().setFont_(AppKit.NSFont.systemFontOfSize_(36))
        self.w.unicodeText._nsObject.cell().setLineBreakMode_(AppKit.NSLineBreakByTruncatingMiddle)
        y += 55
        self.w.copyButton = Button((20, y, 120, 25), "Copy", callback=self.copy_)
        self.w.copyButton.enable(False)

        self.w.open()
        self.w._window.setWindowController_(self)
        self.w._window.setBecomesKeyOnlyIfNeeded_(False)
        self.w._window.makeKeyWindow()

    def show(self):
        if self.w._window is None:
            # we have been closed, let's reconstruct
            self.__init__()
        else:
            self.w.show()

    def searchTextChanged_(self, sender):
        results = []
        terms = sender.get().upper().split()
        if len(terms) == 1:
            m = _unicodePat.match(terms[0])
            if m is not None:
                uni = int(m.group(4), 16)
                if uni < 0x110000:
                    results = [uni]
        if terms:
            uniSets = [set(findPrefix(t)) for t in terms]
            foundSet = uniSets[0]
            for s in uniSets[1:]:
                foundSet &= s
            results += sorted(foundSet)

        self.searchResults = results
        self.w.unicodeList.set([])
        self.appendResults_(500)

    def appendResults_(self, maxResults):
        start = len(self.w.unicodeList)
        unicodeItems = [dict(char=chr(uni),
                             unicode=f"U+{uni:04X}",
                             name=unicodedata.name(chr(uni), ""))
                        for uni in self.searchResults[start:start+maxResults]]
        if len(self.searchResults) > start + maxResults:
            unicodeItems.append(dict(name="...more..."))
        self.w.unicodeList.extend(unicodeItems)

    def listSelectionChanged_(self, sender):
        sel = sender.getSelection()
        if sel and sender[max(sel)]["name"] == "...more...":
            del sender[len(sender) - 1]
            self.appendResults_(500)
            sender.setSelection(sel)
        chars = "".join(chr(self.searchResults[i]) for i in sel)
        self.w.copyButton.enable(bool(chars))
        self.selectedChars = chars
        self.w.unicodeText.set(chars)

    def listDoubleClickCallback_(self, sender):
        app = AppKit.NSApp()
        w = app.mainWindow()
        fr = w.firstResponder()
        if fr is None or not isinstance(fr, AppKit.NSTextView):
            return
        fr.insertText_replacementRange_(self.selectedChars, fr.selectedRange())

    def copy_(self, sender):
        p = AppKit.NSPasteboard.generalPasteboard()
        p.clearContents()
        p.declareTypes_owner_([AppKit.NSPasteboardTypeString], None)
        p.setString_forType_(self.selectedChars, AppKit.NSPasteboardTypeString)
