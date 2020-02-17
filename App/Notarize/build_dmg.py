import os
import subprocess
import sys
import tempfile


appPath = os.path.abspath(sys.argv[1])
appFileName = os.path.basename(appPath)
appName, _ = os.path.splitext(appFileName)

dmgPath = os.path.abspath(sys.argv[2])
if os.path.exists(dmgPath):
    os.remove(dmgPath)


with tempfile.TemporaryDirectory() as imgPath:
    appOnImagePath = os.path.join(imgPath, appFileName)
    # We temporarily _move_ the app, as shutil.copytree() apparently
    # invalidates a couple of the app's code signatures :(
    os.rename(appPath, appOnImagePath)
    try:
        os.symlink("/Applications", os.path.join(imgPath, "Applications"))

        tmpImagePath = tempfile.mktemp(suffix=".dmg")
        try:
            createCommand = [
                "hdiutil", "create", "-fs", "HFS+",
                "-size", "200m",
                "-srcfolder", imgPath,
                "-volname", appName,
                "-format", "UDZO",
                "-quiet",
                tmpImagePath,
            ]
            subprocess.run(createCommand, check=True)

            convertCommand = [
                "hdiutil", "convert", "-format", "UDZO", "-imagekey", "zlib-level=9",
                "-quiet",
                "-o", dmgPath, tmpImagePath,
            ]
            subprocess.run(convertCommand, check=True)
        finally:
            if os.path.exists(tmpImagePath):
                os.remove(tmpImagePath)
    finally:
        os.rename(appOnImagePath, appPath)
