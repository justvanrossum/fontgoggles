import os
from AppKit import , NSDocumentController, NSMenu, NSMenuItem
from Foundation import NSObject, NSURL
from ..misc.decorators import suppressAndLogException


class FGAppDelegate(NSObject):

    filesToOpen = None

    def applicationShouldOpenUntitledFile_(self, app):
        return False

    def application_openFiles_(self, app, files):
        self.queueFilesForOpening_(files)

    def queueFilesForOpening_(self, fileNames):
        if self.filesToOpen is None:
            self.filesToOpen = list(fileNames)
        else:
            self.filesToOpen.extend(fileNames)
        self.performSelector_withObject_afterDelay_("openQueuedFiles", None, 0.2)

    @suppressAndLogException
    def openQueuedFiles(self):
        if self.filesToOpen:
            filesToOpen = [p for p in self.filesToOpen if os.path.isdir(p) or sniffFontType(p)]
            self.filesToOpen = None
            if not filesToOpen:
                return
            # doc = TMProjectDocument.alloc().initWithSourceFiles_(filesToOpen)
            #doc.updateChangeCount_(1)
            # docController.addDocument_(doc)
            # doc.makeWindowControllers()
            project = Project()
            docController = NSDocumentController.sharedDocumentController()
            for path in sorted(filesToOpen):
                project.addSourcePath(path)
                url = NSURL.fileURLWithPath_(path)
                docController.noteNewRecentDocumentURL_(url)
            self.windowController = ProjectWindowController(project)
