from setuptools import setup
import pkg_resources
import os
import datetime
import importlib
import pathlib
import re
import sys
import fontgoggles.mac


appFolder = pathlib.Path(__file__).resolve().parent
os.chdir(appFolder)  # make our parent dir the current dir
creditsSource = appFolder / "Credits.rtf"
creditsDest = appFolder / "Resources" / "English.lproj" / "Credits.rtf"


markerPat = re.compile("<<<([^>]+)>>>")


def fillInPackageVersions(creditsSource, creditsDest):
    credits = creditsSource.read_text()
    pos = 0
    while True:
        m = markerPat.search(credits, pos)
        if m is None:
            break
        pos = m.endpos
        startpos, endpos = m.span()
        packageName = m.group(1)
        if packageName == "python":
            version = sys.version.split()[0]
        elif "." in packageName:
            moduleName = packageName.split(".", 1)[0]
            module = importlib.import_module(moduleName)
            version = eval(packageName, {moduleName: module})
            if isinstance(version, tuple):
                version = ".".join(str(p) for p in version)
        else:
            version = pkg_resources.get_distribution(packageName).version
        credits = credits[:startpos] + f" ({version})" + credits[endpos:]
        pos = startpos
    creditsDest.write_text(credits)


infoplist = dict(
    CFBundleDocumentTypes=[
        dict(
            CFBundleTypeExtensions=["gggls"],
            CFBundleTypeName="FontGoggles Project File",
            CFBundleTypeRole="Editor",
            NSDocumentClass="FGDocument",
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
    LSMinimumSystemVersion="10.13",
    CFBundleShortVersionString=fontgoggles.__version__,
    CFBundleVersion=fontgoggles.__version__,
    CFBundleIconFile="fontgoggles.icns",
    NSHumanReadableCopyright=f"Copyright © 2019-{datetime.datetime.now().year} The FontGoggles Project Authors.",
    NSPrincipalClass="NSApplication",
    NSRequiresAquaSystemAppearance=False,
    # ATSApplicationFontsPath="Fonts/",
)


appName = "FontGoggles"

turboLibOriginalPath = os.path.join(os.path.dirname(fontgoggles.mac.__file__),
                                    "libmakePathFromOutline.dylib")
turboLibPath = os.path.join(appFolder, "libmakePathFromOutline.dylib")

fillInPackageVersions(creditsSource, creditsDest)


try:
    # We don't want our dylib to be included in the library zip file, instead
    # it should go into the app Frameworks location. We temporarily move the
    # dylib to the App folder to accomplish this.
    os.rename(turboLibOriginalPath, turboLibPath)
    setup(
        data_files=['Resources/English.lproj', 'Resources/errorPatternImage.png'],
        app=[f"{appName}.py"],
        packages=[],
        options=dict(py2app=dict(
            iconfile="Resources/fontgoggles.icns",
            plist=infoplist,
            packages=[
                "fontgoggles",
                "pkg_resources",
                "numpy",
            ],
            excludes=[
                "cffsubr",
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
