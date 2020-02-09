import os
import pickle
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib import TTFont, newTable
from fontTools import varLib


def compileDSToFont(dsPath, ttFolder):
    doc = DesignSpaceDocument.fromfile(dsPath)
    doc.findDefault()

    ufoPathToTTPath = getTTPaths(doc, ttFolder)

    for source in doc.sources:
        if source.layerName is None:
            ttPath = ufoPathToTTPath[source.path]
            if not os.path.exists(ttPath):
                raise FileNotFoundError(ttPath)
            source.font = TTFont(ttPath, lazy=False)

    assert doc.default.font is not None
    doc.default.font["name"] = newTable("name")  # This is the template for the VF, and needs a name table

    if any(s.layerName is not None for s in doc.sources):
        fb = FontBuilder(unitsPerEm=doc.default.font["head"].unitsPerEm)
        fb.setupGlyphOrder(doc.default.font.getGlyphOrder())
        fb.setupPost()  # This makes sure we store the glyph names
        font = fb.font
        for source in doc.sources:
            if source.font is None:
                source.font = font

    ttFont, masterModel, _ = varLib.build(doc, exclude=['MVAR', 'HVAR', 'VVAR', 'STAT'])

    # Our client needs the masterModel, so we save a pickle into the font
    ttFont["MPcl"] = newTable("MPcl")
    ttFont["MPcl"].data = pickle.dumps(masterModel)

    return ttFont


def compileDSToPath(dsPath, ttFolder, ttPath):
    ttFont = compileDSToFont(dsPath, ttFolder)
    ttFont.save(ttPath, reorderTables=False)


def getTTPaths(doc, ttFolder):
    ufoPaths = sorted({s.path for s in doc.sources if s.layerName is None})
    return {ufoPath: os.path.join(ttFolder, f"master_{index}.ttf")
            for index, ufoPath in enumerate(ufoPaths)}
