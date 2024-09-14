import pathlib
import shutil
from fontTools.pens.recordingPen import RecordingPointPen
from fontTools.ufoLib import UFOReaderWriter
from fontTools.ufoLib.glifLib import Glyph
from fontgoggles.font.ufoFont import UFOState
from fontgoggles.compile.ufoCompiler import fetchGlyphInfo
from testSupport import getFontPath


def test_getUpdateInfo(tmpdir):
    ufoSource = getFontPath("MutatorSansBoldWideMutated.ufo")
    ufoPath = shutil.copytree(ufoSource, tmpdir / "test.ufo")
    reader = UFOReaderWriter(ufoPath, validate=False)
    glyphSet = reader.getGlyphSet()
    widths, cmap, unicodes, anchors = fetchGlyphInfo(glyphSet, ufoPath)

    state = UFOState(reader, glyphSet, getUnicodesAndAnchors=lambda: (unicodes, anchors))

    feaPath = pathlib.Path(reader.fs.getsyspath("/features.fea"))
    feaPath.touch()

    state = state.newState()
    (needsFeaturesUpdate, needsGlyphUpdate, needsInfoUpdate, needsCmapUpdate,
     needsLibUpdate) = state.getUpdateInfo()
    assert needsFeaturesUpdate
    assert not needsGlyphUpdate
    assert not needsInfoUpdate
    assert not needsCmapUpdate

    infoPath = pathlib.Path(reader.fs.getsyspath("/fontinfo.plist"))
    infoPath.touch()

    state = state.newState()
    (needsFeaturesUpdate, needsGlyphUpdate, needsInfoUpdate, needsCmapUpdate,
     needsLibUpdate) = state.getUpdateInfo()
    assert not needsFeaturesUpdate
    assert not needsGlyphUpdate
    assert needsInfoUpdate
    assert not needsCmapUpdate

    glyph = Glyph("A", None)
    ppen = RecordingPointPen()
    glyphSet.readGlyph("A", glyph, ppen)
    glyph.anchors[0]["x"] = 123
    glyphSet.writeGlyph("A", glyph, ppen.replay)

    state = state.newState()
    (needsFeaturesUpdate, needsGlyphUpdate, needsInfoUpdate, needsCmapUpdate,
     needsLibUpdate) = state.getUpdateInfo()
    assert needsFeaturesUpdate
    assert needsGlyphUpdate
    assert not needsInfoUpdate
    assert not needsCmapUpdate

    glyph = Glyph("A", None)
    ppen = RecordingPointPen()
    glyphSet.readGlyph("A", glyph, ppen)
    glyph.unicodes = [123]
    glyphSet.writeGlyph("A", glyph, ppen.replay)

    state = state.newState()
    (needsFeaturesUpdate, needsGlyphUpdate, needsInfoUpdate, needsCmapUpdate,
     needsLibUpdate) = state.getUpdateInfo()
    assert not needsFeaturesUpdate
    assert needsGlyphUpdate
    assert not needsInfoUpdate
    assert needsCmapUpdate

    glyph = Glyph("A", None)
    ppen = RecordingPointPen()
    glyphSet.readGlyph("A", glyph, ppen)
    glyph.width += 123
    glyphSet.writeGlyph("A", glyph, ppen.replay)
    kerning = reader.readKerning()
    kerning["T", "comma"] = -123
    reader.writeKerning(kerning)

    state = state.newState()
    (needsFeaturesUpdate, needsGlyphUpdate, needsInfoUpdate, needsCmapUpdate,
     needsLibUpdate) = state.getUpdateInfo()
    assert needsFeaturesUpdate
    assert needsGlyphUpdate
    assert not needsInfoUpdate
    assert not needsCmapUpdate
