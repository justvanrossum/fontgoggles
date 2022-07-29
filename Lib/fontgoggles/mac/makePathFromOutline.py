import ctypes
import pathlib

import objc
import Foundation


class NSPoint(ctypes.Structure):
    _fields_ = [('x', ctypes.c_double),
                ('y', ctypes.c_double)]

NSPoint_p = ctypes.POINTER(NSPoint)
c_char_p = ctypes.POINTER(ctypes.c_char)
c_short_p = ctypes.POINTER(ctypes.c_short)


_libName = "libmakePathFromOutline.dylib"
_mainBundle = Foundation.NSBundle.mainBundle()
_libPath = pathlib.Path(_mainBundle.privateFrameworksPath()) / _libName
if not _libPath.exists():
    # This is for when we're running in an py2app -A bundle or outside of an app bundle,
    # such as with pytest
    _libPath = pathlib.Path(__file__).resolve().parent / _libName
    assert _libPath.exists(), f"can't find {_libName}"

_lib = ctypes.cdll.LoadLibrary(_libPath)

_makePathFromArrays = _lib.makePathFromArrays
_makePathFromArrays.argtypes = [ctypes.c_short,
                                ctypes.c_short,
                                NSPoint_p,
                                c_char_p,
                                c_short_p]
_makePathFromArrays.restype = ctypes.c_void_p


def makePathFromArrays(points, tags, contours):
    import numpy

    n_contours = len(contours)
    n_points = len(tags)
    assert len(points) >= n_points
    assert points.shape[1:] == (2,)
    if points.dtype != numpy.double:
        points = points.astype(numpy.double)
    assert tags.dtype == numpy.byte
    assert contours.dtype == numpy.short
    path = objc.objc_object(
        c_void_p=_makePathFromArrays(
            n_contours,
            n_points,
            points.ctypes.data_as(NSPoint_p),
            tags.ctypes.data_as(c_char_p),
            contours.ctypes.data_as(c_short_p)))
    # Not sure why, but the path object comes back with a retain count too many.
    # In _makePathFromArrays(), we do [[NSBezierPath alloc] init], so that's one.
    # We pretty much take over that reference, but I think objc.objc_object()
    # assumes it needs to own it, too.
    path.release()
    return path
