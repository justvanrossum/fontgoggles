import ctypes
import functools
import pathlib

import freetype
import objc


_libPath = pathlib.Path(__file__).resolve().parent / "makePathFromOutline.dylib"
_lib = ctypes.cdll.LoadLibrary(_libPath)

_makePathFromOutline = _lib.makePathFromOutline
_makePathFromOutline.argtypes = [ctypes.POINTER(freetype.ft_structs.FT_Outline)]
_makePathFromOutline.restype = ctypes.c_void_p


def makePathFromOutline(outline):
    return objc.objc_object(c_void_p=_makePathFromOutline(outline))
