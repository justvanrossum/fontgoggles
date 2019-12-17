import re
import unicodedata
import AppKit
from vanilla import *
from ..misc.unicodeNameList import findPrefix


_unicodePat = re.compile(r"(([u]\+)|(0x))?([0-9a-f]+)$", re.IGNORECASE)


class UnicodePicker:

    def __init__(self):
        self.searchResults = []
        self.selectedChars = ""

        self.w = FloatingWindow((300, 400), "Unicode Picker", minSize=(250, 300),
                                autosaveName="UnicodePicker")
        y = 15
        self.w.searchField = EditText((20, y, -20, 25),
                                      placeholder="Search Unicode name or value",
                                      callback=self.searchTextChanged)

        y += 40
        columnDescriptions = [
            dict(title="unicode", width=80),
            dict(title="name"),
        ]
        self.w.unicodeList = List((0, y, 0, -100), [], columnDescriptions=columnDescriptions,
                                  selectionCallback=self.listSelectionChanged,
                                  doubleClickCallback=self.listDoubleClickCallback)
        y = -95
        self.w.unicodeText = TextBox((20, y, -10, 55), "")
        self.w.unicodeText._nsObject.cell().setFont_(AppKit.NSFont.systemFontOfSize_(36))
        y += 55
        self.w.copyButton = Button((20, y, 120, 25), "Copy", callback=self.copyButtonCallback)
        self.w.copyButton.enable(False)

        self.w.open()
        self.w._window.setBecomesKeyOnlyIfNeeded_(False)
        self.w._window.makeKeyWindow()

    def show(self):
        if self.w._window is None:
            # we have been closed, let's reconstruct
            self.__init__()
        else:
            self.w.show()

    def searchTextChanged(self, sender):
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
        unicodeItems = [dict(unicode=f"U+{uni:04X}", name=unicodedata.name(chr(uni), "")) for uni in results]
        if len(unicodeItems) > 100:
            unicodeItems = unicodeItems[:100] + [dict(name="...more...")]
        self.w.unicodeList.set(unicodeItems)

    def listSelectionChanged(self, sender):
        chars = "".join(chr(self.searchResults[i]) for i in sender.getSelection())
        self.w.copyButton.enable(bool(chars))
        self.selectedChars = chars
        self.w.unicodeText.set(chars)

    def listDoubleClickCallback(self, sender):
        app = AppKit.NSApp()
        w = app.mainWindow()
        fr = w.firstResponder()
        if fr is None or not isinstance(fr, AppKit.NSTextView):
            return
        fr.insertText_replacementRange_(self.selectedChars, fr.selectedRange())

    def copyButtonCallback(self, sender):
        p = AppKit.NSPasteboard.generalPasteboard()
        p.clearContents()
        p.declareTypes_owner_([AppKit.NSPasteboardTypeString], None)
        p.setString_forType_(self.selectedChars, AppKit.NSPasteboardTypeString)
