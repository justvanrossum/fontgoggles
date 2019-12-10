import ctypes
import pathlib

import freetype
import objc
import Foundation


_libName = "makePathFromOutline.dylib"
_mainBundle = Foundation.NSBundle.mainBundle()
_searchFolders = [
    pathlib.Path(__file__).resolve().parent,
    pathlib.Path(_mainBundle.privateFrameworksURL().path()),
]

for _folder in _searchFolders:
    _libPath = _folder / _libName
    if _libPath.exists():
        _lib = ctypes.cdll.LoadLibrary(_libPath)
        _makePathFromOutline = _lib.makePathFromOutline
        _makePathFromOutline.argtypes = [ctypes.POINTER(freetype.ft_structs.FT_Outline)]
        _makePathFromOutline.restype = ctypes.c_void_p
        break
else:
    _makePathFromOutline = None


def makePathFromOutline(outline):
    path = objc.objc_object(c_void_p=_makePathFromOutline(outline))
    # Not sure why, but the path object comes back with a retain count too many.
    # In _makePathFromOutline(), we do [[NSBezierPath alloc] init], so that's one.
    # We pretty much take over that reference, but I think objc.objc_object()
    # assumes it needs to own it, too.
    path.release()
    return path
