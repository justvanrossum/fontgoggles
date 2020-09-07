from setuptools import setup
import os
import datetime
import fontgoggles.mac


appFolder = os.path.dirname(os.path.abspath(__file__))
os.chdir(appFolder)  # make our parent dir the current dir


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
    LSMinimumSystemVersion="10.10",
    CFBundleShortVersionString=fontgoggles.__version__,
    CFBundleVersion=fontgoggles.__version__,
    CFBundleIconFile="fontgoggles.icns",
    NSHumanReadableCopyright=f"Copyright © 2019-{datetime.datetime.now().year} The FontGoggles Project Authors.",
    NSPrincipalClass="NSApplication",
    NSRequiresAquaSystemAppearance=False,
    # ATSApplicationFontsPath="Fonts/",
)


appName = "FontGoggles"

setup(
    data_files=['Resources/English.lproj', 'Resources/errorPatternImage.png'],
    app=[f"{appName}.py"],
    options=dict(py2app=dict(
        iconfile="Resources/fontgoggles.icns",
        plist=infoplist,
        packages=[
            "fontgoggles",
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
    )),
)
