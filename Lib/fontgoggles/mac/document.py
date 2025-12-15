import json
import pathlib
import objc
import AppKit
from objc import super

from ..project import Project
from .mainWindow import FGMainWindowController
from ..font import defaultSortSpec, sortedFontPathsAndNumbers
from .fileObserver import getFileObserver


class FGDocument(AppKit.NSDocument):

    def __new__(cls):
        return cls.alloc().init()

    def init(self):
        self = super().init()
        self.project = Project()
        return self

    def addSourceFiles_(self, paths):
        paths = [pathlib.Path(path) for path in paths]
        for fontPath, fontNumber in sortedFontPathsAndNumbers(paths, defaultSortSpec):
            self.project.addFont(fontPath, fontNumber)

    def makeWindowControllers(self):
        controller = FGMainWindowController(self.project)
        self.addWindowController_(controller)

    def writeSafelyToURL_ofType_forSaveOperation_error_(self, url, tp, so, error):
        self._savePath = url.path()
        return super().writeSafelyToURL_ofType_forSaveOperation_error_(url, tp, so, error)

    def dataOfType_error_(self, type, error):
        rootPath = pathlib.Path(self._savePath).parent
        for controller in self.windowControllers():
            controller.syncUISettingsWithProject()
        return AppKit.NSData.dataWithData_(self.project.asJSON(rootPath)), error

    def readFromData_ofType_error_(self, data, type, error):
        documentPath = str(self.fileURL().path())
        rootPath = pathlib.Path(documentPath).parent
        self.project = Project.fromJSON(bytes(data), rootPath)
        obs = getFileObserver()
        obs.addObserver(documentPath, self._projectFileChangedOnDisk)
        return True, None

    @objc.python_method
    def _projectFileChangedOnDisk(self, oldPath, newPath, wasModified):
        if not wasModified:
            return
        rootPath = pathlib.Path(newPath).parent
        with open(newPath, "rb") as f:
            dataDict = json.load(f)
        self.project.updateFromDict(dataDict, rootPath)
        for controller in self.windowControllers():
            controller.syncFromProject()

    def revertToContentsOfURL_ofType_error_(self, url, type, error):
        for controller in list(self.windowControllers()):
            self.removeWindowController_(controller)
            controller.w.close()
            controller.close()
        success, error = self.readFromURL_ofType_error_(url, type, None)
        if success:
            self.makeWindowControllers()
        return True, error

    def fileModificationDate(self):
        # This is a workaround to avoid the "The file has been changed by another application"
        # message, if we have reloaded the project after an external change.
        fileManager = AppKit.NSFileManager.defaultManager()
        attrs, error = fileManager.attributesOfItemAtPath_error_(self.fileURL().path(), None)
        return attrs[AppKit.NSFileModificationDate]
