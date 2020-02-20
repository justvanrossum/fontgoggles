import pathlib
import AppKit

from ..project import Project
from .mainWindow import FGMainWindowController
from ..font import defaultSortSpec, sortedFontPathsAndNumbers


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
            controller.syncUIStateWithProject()
        return AppKit.NSData.dataWithData_(self.project.asJSON(rootPath)), error

    def readFromData_ofType_error_(self, data, type, error):
        rootPath = pathlib.Path(self.fileURL().path()).parent
        self.project = Project.fromJSON(bytes(data), rootPath)
        return True, None
