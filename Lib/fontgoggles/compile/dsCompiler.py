import os
import pickle
import sys
from collections import defaultdict
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.designspaceLib.split import splitVariableFonts
from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib import TTFont, newTable
from fontTools import varLib
from fontTools.ufoLib import UFOReader
from fontTools.varLib.errors import VarLibError
from ufo2ft.featureCompiler import VariableFeatureCompiler
from .ufoCompiler import MinimalFontObject


def compileDSToFont(dsPath, fontNumber, ttFolder, shouldCompileFeatures):
    fontNumber = int(fontNumber)
    docs = list(splitVariableFonts(DesignSpaceDocument.fromfile(dsPath)))
    _, doc = docs[fontNumber]

    ufoPathToTTPath = getTTPaths(doc, ttFolder)

    for source in doc.sources:
        if source.layerName is None:
            ttPath = ufoPathToTTPath[source.path]
            if not os.path.exists(ttPath):
                raise FileNotFoundError(ttPath)
            source.font = TTFont(ttPath, lazy=False)

    assert doc.default.font is not None
    if "name" not in doc.default.font:
        doc.default.font["name"] = newTable("name")  # This is the template for the VF, and needs a name table

    if any(s.layerName is not None for s in doc.sources):
        fb = FontBuilder(unitsPerEm=doc.default.font["head"].unitsPerEm)
        fb.setupGlyphOrder(doc.default.font.getGlyphOrder())
        fb.setupCharacterMap({})
        fb.setupPost()  # This makes sure we store the glyph names
        font = fb.font
        for source in doc.sources:
            if source.font is None:
                source.font = font

    exclude = ['HVAR', 'VVAR', 'STAT']
    if shouldCompileFeatures:
        exclude.extend(['GSUB', 'GPOS', 'GDEF'])

    try:
        ttFont, masterModel, _ = varLib.build(doc, exclude=exclude)
    except VarLibError as e:
        if 'GSUB' in e.args:
            extraExclude = ['GSUB']
        elif 'GPOS' in e.args:
            extraExclude = ['GPOS', 'GDEF']
        else:
            raise
        print(f"{e!r}", file=sys.stderr)
        print(f"Error while building {extraExclude[0]} table, trying again without {' and '.join(extraExclude)}.",
              file=sys.stderr)
        ttFont, masterModel, _ = varLib.build(doc, exclude=['MVAR', 'HVAR', 'VVAR', 'STAT'] + extraExclude)

    if shouldCompileFeatures:
        try:
            compileVariableFeatures(doc, ttFont)
        except Exception as e:
            print(f"{e!r}", file=sys.stderr)
            print(f"Error while adding features", file=sys.stderr)
            # raise

    # Our client needs the masterModel, so we save a pickle into the font
    ttFont["MPcl"] = newTable("MPcl")
    ttFont["MPcl"].data = pickle.dumps(masterModel)

    return ttFont


def compileDSToPath(dsPath, fontNumber, ttFolder, ttPath, shouldCompileFeatures):
    ttFont = compileDSToFont(dsPath, fontNumber, ttFolder, shouldCompileFeatures)
    ttFont.save(ttPath, reorderTables=False)


def getTTPaths(doc, ttFolder):
    ufoPaths = sorted({s.path for s in doc.sources if s.layerName is None})
    return {ufoPath: os.path.join(ttFolder, f"master_{index}.ttf")
            for index, ufoPath in enumerate(ufoPaths)}


def compileVariableFeatures(dsDoc, ttFont):
    # Adapted from ufo2ft's compile_variable_features
    dsDoc = dsDoc.deepcopyExceptFonts()
    for source in dsDoc.sources:
        anchors = pickle.loads(source.font["FGAx"].data) if "FGAx" in source.font else {}

        revCmap = getRevCmapFromTTFont(source.font)

        ufoPath = source.path
        reader = UFOReader(ufoPath, validate=False)
        source.font = MinimalFontObject(
            ufoPath, reader, source.layerName, {}, revCmap, anchors
        )

    defaultUFO = dsDoc.findDefault().font

    featureCompiler = VariableFeatureCompiler(
        defaultUFO,
        dsDoc,
        ttFont=ttFont,
        glyphSet=None,
        feaIncludeDir=os.path.dirname(ufoPath),
    )
    featureCompiler.compile()

    # Add feature variations from dsDoc.rules
    varLib.addGSUBFeatureVariations(ttFont, dsDoc)


def getRevCmapFromTTFont(ttFont):
    cmap = ttFont.getBestCmap()
    revCmap = defaultdict(list)
    for codePoint, glyphName in cmap.items():
        revCmap[glyphName].append(codePoint)
    return dict(revCmap)
