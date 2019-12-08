import os
from AppKit import NSDocumentController
from Foundation import NSObject, NSURL
from ..misc.decorators import suppressAndLogException


def sniffFontType(path):
    # stub
    return True


class FGAppDelegate(NSObject):

    filesToOpen = None

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
            filesToOpen = [p for p in self.filesToOpen if os.path.isdir(p) or sniffFontType(p)]
            self.filesToOpen = None
            if not filesToOpen:
                return
            print(filesToOpen)
            # project = Project()
            # docController = NSDocumentController.sharedDocumentController()
            # for path in sorted(filesToOpen):
            #     project.addSourcePath(path)
            #     url = NSURL.fileURLWithPath_(path)
            #     docController.noteNewRecentDocumentURL_(url)
            # self.windowController = ProjectWindowController(project)
