import os
import pathlib
from AppKit import NSDocumentController
from Foundation import NSObject, NSURL
from vanilla.dialogs import getFile
from ..font import sniffFontType, fileTypes
from ..misc.decorators import suppressAndLogException
from .document import FGDocument


class FGAppDelegate(NSObject):

    filesToOpen = None
    unicodePicker = None

    def openDocument_(self, sender):
        result = getFile(allowsMultipleSelection=True,
                         fileTypes=fileTypes + ["gggls"])  # resultCallback=self.getFileResultCallback_)
        # NOTE: ideally we would use a result callback, but vanilla's
        # getFile() only supports result callbacks in the presence of
        # parent window, which we obviously do not have here.
        # Also note: we can't use NSDocumentController's openDocument_
        # as it assumes one file per document.
        if result:
            self.application_openFiles_(None, result)

    def applicationShouldOpenUntitledFile_(self, app):
        return True

    def application_openFiles_(self, app, fileNames):
        nonProjectFileNames = [f for f in fileNames if not f.endswith(".gggls")]
        projectFileNames = [f for f in fileNames if f.endswith(".gggls")]

        if self.filesToOpen is None:
            self.filesToOpen = list(nonProjectFileNames)
        else:
            self.filesToOpen.extend(nonProjectFileNames)
        if self.filesToOpen:
            # When the user drops multiple files on the app, application_openFiles_
            # is sometimes called multiple times. Let's delay a bit and see if
            # more files came in in the meantime.
            self.performSelector_withObject_afterDelay_("openQueuedFiles", None, 0.2)
        if projectFileNames:
            docController = NSDocumentController.sharedDocumentController()
            for path in projectFileNames:
                url = NSURL.fileURLWithPath_(path)
                docController.openDocumentWithContentsOfURL_display_completionHandler_(
                            url, True, None)

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
