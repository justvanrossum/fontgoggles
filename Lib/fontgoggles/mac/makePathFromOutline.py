import ctypes
import pathlib

import freetype
import numpy
import objc
import Foundation


FT_Vector_p = ctypes.POINTER(freetype.ft_structs.FT_Vector)
FT_Outline_p = ctypes.POINTER(freetype.ft_structs.FT_Outline)
c_char_p = ctypes.POINTER(ctypes.c_char)
c_short_p = ctypes.POINTER(ctypes.c_short)


_libName = "libmakePathFromOutline.dylib"
_mainBundle = Foundation.NSBundle.mainBundle()
_searchFolders = [
    pathlib.Path(_mainBundle.resourcePath()),
    pathlib.Path(_mainBundle.privateFrameworksPath()),
    pathlib.Path(__file__).resolve().parent,
]

for _folder in _searchFolders:
    _libPath = _folder / _libName
    if _libPath.exists():
        _lib = ctypes.cdll.LoadLibrary(_libPath)

        _makePathFromOutline = _lib.makePathFromOutline
        _makePathFromOutline.argtypes = [FT_Outline_p]
        _makePathFromOutline.restype = ctypes.c_void_p

        _makePathFromArrays = _lib.makePathFromArrays
        _makePathFromArrays.argtypes = [ctypes.c_short,
                                        ctypes.c_short,
                                        FT_Vector_p,
                                        c_char_p,
                                        c_short_p]
        _makePathFromArrays.restype = ctypes.c_void_p

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


def makePathFromArrays(points, tags, contours):
    n_contours = len(contours)
    n_points = len(tags)
    assert len(points) >= n_points
    assert points.shape[1:] == (2,)
    if points.dtype != numpy.long:
        points = numpy.floor(points + [0.5, 0.5])
        points = points.astype(numpy.long)
    assert tags.dtype == numpy.byte
    assert contours.dtype == numpy.short
    path = objc.objc_object(
        c_void_p=_makePathFromArrays(
            n_contours,
            n_points,
            points.ctypes.data_as(FT_Vector_p),
            tags.ctypes.data_as(c_char_p),
            contours.ctypes.data_as(c_short_p)))
    # See comment in makePathFromOutline()
    path.release()
    return path
