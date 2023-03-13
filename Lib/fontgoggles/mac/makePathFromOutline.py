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

_makePath = _lib.makePath
_makePath.restype = ctypes.c_void_p

PyCapsule_New = ctypes.pythonapi.PyCapsule_New
PyCapsule_New.restype = ctypes.py_object
PyCapsule_New.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p)

move_to_capsule = PyCapsule_New(_lib.move_to, None, None)
line_to_capsule = PyCapsule_New(_lib.line_to, None, None)
cubic_to_capsule = PyCapsule_New(_lib.cubic_to, None, None)
close_path_capsule = PyCapsule_New(_lib.close_path, None, None)

from uharfbuzz import DrawFuncs
funcs = DrawFuncs()
funcs.set_move_to_func(move_to_capsule)
funcs.set_line_to_func(line_to_capsule)
funcs.set_cubic_to_func(cubic_to_capsule)
funcs.set_close_path_func(close_path_capsule)


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

def makePathFromGlyph(font, gid):

    path_p = _makePath()
    path_capsule = PyCapsule_New(path_p, None, None)

    font.draw_glyph(gid, funcs, path_capsule)

    path = objc.objc_object(c_void_p=path_p)
    # See comment in makePathFromArrays()
    path.release()

    return path
