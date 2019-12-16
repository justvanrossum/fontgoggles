import pathlib
import AppKit

from ..project import Project
from .mainWindow import FGMainWindowController
from ..font import getOpener, sniffFontType


class FGDocument(AppKit.NSDocument):

    def __new__(cls, *args, **kwargs):
        return cls.alloc().init()

    def __init__(self):
        self.project = Project()

    def addSourceFiles_(self, paths):
        for path in paths:
            path = pathlib.Path(path)
            if sniffFontType(path) is None and path.is_dir():
                for child in path.iterdir():
                    if sniffFontType(child) is not None:
                        self.addSourceFile_(child)
            else:
                self.addSourceFile_(path)

    def addSourceFile_(self, path):
        numFonts, opener = getOpener(path)
        for i in range(numFonts(path)):
            self.project.addFont(path, i)

    def makeWindowControllers(self):
        controller = FGMainWindowController(self.project)
        self.addWindowController_(controller)
