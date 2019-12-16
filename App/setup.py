from distutils.core import setup
import os
import datetime
import glob


os.chdir(os.path.dirname(os.path.abspath(__file__)))  # make our parent dir the current dir


infoplist = dict(
    CFBundleDocumentTypes = [
        dict(
            CFBundleTypeExtensions=["ufo"],
            CFBundleTypeName="Unified Font Object",
            CFBundleTypeRole="Viewer",
            LSTypeIsPackage=True,
        ),
        dict(
            CFBundleTypeExtensions=["ttf", "otf", "woff", "woff2", "otc", "ttc", "dfont"],
            CFBundleTypeName="OpenType Font",
            CFBundleTypeRole="Viewer",
        ),
        # dict(
        #     CFBundleTypeExtensions=["glyphs"],
        #     CFBundleTypeName="GlyphsApp Source File",
        #     CFBundleTypeRole="Viewer",
        # ),
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
    CFBundleIdentifier="com.github.googlefonts.FontGoggles",
    LSMinimumSystemVersion="10.10",
    CFBundleShortVersionString="0.1a",
    CFBundleVersion="0.1a",
    CFBundleIconFile="fontgoggles.icns",
    NSHumanReadableCopyright=f"Copyright © {datetime.datetime.now().year} Just van Rossum.\nAll rights reserved.",
    NSPrincipalClass="NSApplication",
    # ATSApplicationFontsPath="Fonts/",
)

dataFiles = [
        '../Lib/fontgoggles/mac/libmakePathFromOutline.dylib',
        'Resources/English.lproj',
        # 'Resources/Fonts',
] + glob.glob("Resources/*.pdf")

appName = "FontGoggles"

setup(
    data_files=dataFiles,
    app=[f"{appName}.py"],
    options=dict(py2app=dict(
        # iconfile="Resources/fontgoggles.icns",
        plist=infoplist,
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
