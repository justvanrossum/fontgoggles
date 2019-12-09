import ctypes
import functools
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
    return objc.objc_object(c_void_p=_makePathFromOutline(outline))
