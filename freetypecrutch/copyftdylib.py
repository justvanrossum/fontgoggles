import importlib
import os
import shutil

spec = importlib.util.find_spec("freetype")
assert spec is not None

dylibFileName = "libfreetype.dylib"
dylibSource = os.path.join(os.path.dirname(os.path.abspath(__file__)), dylibFileName)
freetypeFolder = os.path.dirname(spec.origin)
dylibDest = os.path.join(freetypeFolder, dylibFileName)

shutil.copy2(dylibSource, dylibDest)
