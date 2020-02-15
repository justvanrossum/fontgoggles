from setuptools import setup
import os
import datetime
import fontgoggles.mac


appFolder = os.path.dirname(os.path.abspath(__file__))
os.chdir(appFolder)  # make our parent dir the current dir


infoplist = dict(
    CFBundleDocumentTypes = [
        dict(
            CFBundleTypeExtensions = ["gggls"],
            CFBundleTypeName = "FontGoggles Project File",
            CFBundleTypeRole = "Editor",
            NSDocumentClass = "FGDocument",
        ),
        dict(
            CFBundleTypeExtensions=["ufo", "ufoz"],
            CFBundleTypeName="Unified Font Object",
            CFBundleTypeRole="Viewer",
            LSTypeIsPackage=True,
        ),
        dict(
            CFBundleTypeExtensions=["ttf", "otf", "otc", "ttc", "dfont", "woff", "woff2"],
            CFBundleTypeName="OpenType Font",
            CFBundleTypeRole="Viewer",
        ),
        dict(
            CFBundleTypeExtensions=["ttx"],
            CFBundleTypeName="TTX Source File",
            CFBundleTypeRole="Viewer",
        ),
        dict(
            CFBundleTypeExtensions=["designspace"],
            CFBundleTypeName="Designspace File",
            CFBundleTypeRole="Viewer",
        ),
        dict(
            CFBundleTypeExtensions=["*"],
            CFBundleTypeName="Any File",
            CFBundleTypeRole="Viewer",
        ),
    ],
    CFBundleName="FontGoggles",
    CFBundleIdentifier="com.github.justvanrossum.FontGoggles",
    LSMinimumSystemVersion="10.10",
    CFBundleShortVersionString="0.9",
    CFBundleVersion="0.9",
    CFBundleIconFile="fontgoggles.icns",
    NSHumanReadableCopyright=f"Copyright © {datetime.datetime.now().year} Just van Rossum.",
    NSPrincipalClass="NSApplication",
    NSRequiresAquaSystemAppearance=False,
    # ATSApplicationFontsPath="Fonts/",
)


appName = "FontGoggles"

turboLibOriginalPath = os.path.join(os.path.dirname(fontgoggles.mac.__file__),
                                    "libmakePathFromOutline.dylib")
turboLibPath = os.path.join(appFolder, "libmakePathFromOutline.dylib")

try:
    # We don't want our dylib to be included in the library zip file, instead
    # it should go into the app Frameworks location. We temporarily move the
    # dylib to the App folder to accomplish this.
    os.rename(turboLibOriginalPath, turboLibPath)
    setup(
        data_files=['Resources/English.lproj'],
        app=[f"{appName}.py"],
        options=dict(py2app=dict(
            iconfile="Resources/fontgoggles.icns",
            plist=infoplist,
            packages=[
                "fontgoggles",
                "freetype",
                "pkg_resources",
            ],
            excludes=[
                "scipy",
                "matplotlib",
                "PIL",
                "pygame",
                "wx",
                "test",
                ],
            frameworks=[turboLibPath],
        )),
    )
finally:
    # Move the dylib back to its original location
    os.rename(turboLibPath, turboLibOriginalPath)
