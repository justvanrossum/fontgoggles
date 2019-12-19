import pathlib
import AppKit

from ..project import Project
from .mainWindow import FGMainWindowController
from ..font import sortedFontPathsAndNumbers


class FGDocument(AppKit.NSDocument):

    def __new__(cls, *args, **kwargs):
        return cls.alloc().init()

    def __init__(self):
        self.project = Project()

    def addSourceFiles_(self, paths):
        paths = [pathlib.Path(path) for path in paths]
        for fontPath, fontNumber in sortedFontPathsAndNumbers(paths):
            self.project.addFont(fontPath, fontNumber)

    def makeWindowControllers(self):
        controller = FGMainWindowController(self.project)
        self.addWindowController_(controller)
