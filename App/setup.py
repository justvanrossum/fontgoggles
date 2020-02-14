from setuptools import setup
import os
import datetime
import fontgoggles.mac


os.chdir(os.path.dirname(os.path.abspath(__file__)))  # make our parent dir the current dir


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

setup(
    data_files=['Resources/English.lproj'],
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
        frameworks=[
            os.path.join(os.path.dirname(fontgoggles.mac.__file__), "libmakePathFromOutline.dylib"),
        ]
    )),
)
