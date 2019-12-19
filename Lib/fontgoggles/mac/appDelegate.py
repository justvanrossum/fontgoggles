import os
import pathlib
from AppKit import NSDocumentController
from Foundation import NSObject, NSURL
from vanilla.dialogs import getFile
from ..font import sniffFontType
from ..misc.decorators import suppressAndLogException
from .document import FGDocument


class FGAppDelegate(NSObject):

    filesToOpen = None
    unicodePicker = None

    def openDocument_(self, sender):
        result = getFile(allowsMultipleSelection=True,
                fileTypes=["ttf", "otf", "ufo", "ufoz"])
                # resultCallback=self.getFileResultCallback_)
        # NOTE: ideally we would use a result callback, but vanilla's
        # getFile() only supports result callbacks in the presence of
        # parent window, which we obviously do not have here.
        if result:
            self.application_openFiles_(None, result)

    def applicationShouldOpenUntitledFile_(self, app):
        return False

    def application_openFiles_(self, app, fileNames):
        if self.filesToOpen is None:
            self.filesToOpen = list(fileNames)
        else:
            self.filesToOpen.extend(fileNames)
        # When the user drops multiple files on the app, application_openFiles_
        # is sometimes called multiple times. Let's delay a bit and see if
        # more files came in in the meantime.
        self.performSelector_withObject_afterDelay_("openQueuedFiles", None, 0.2)

    @suppressAndLogException
    def openQueuedFiles(self):
        if self.filesToOpen:
            filesToOpen = [p for p in self.filesToOpen
                           if os.path.isdir(p) or sniffFontType(pathlib.Path(p))]
            self.filesToOpen = None
            if not filesToOpen:
                return

            filesToOpen = sorted(filesToOpen)

            docController = NSDocumentController.sharedDocumentController()
            doc = FGDocument()
            doc.addSourceFiles_(filesToOpen)
            docController.addDocument_(doc)
            doc.makeWindowControllers()

            for path in filesToOpen:
                url = NSURL.fileURLWithPath_(path)
                docController.noteNewRecentDocumentURL_(url)

    def showUnicodePicker_(self, sender):
        from .unicodePicker import UnicodePicker
        if self.unicodePicker is not None:
            self.unicodePicker.show()
        else:
            self.unicodePicker = UnicodePicker()
