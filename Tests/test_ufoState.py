import pathlib
import shutil
from fontTools.pens.recordingPen import RecordingPointPen
from fontTools.ufoLib import UFOReader
from fontTools.ufoLib.glifLib import Glyph
from fontgoggles.font.ufoFont import UFOState
from fontgoggles.compile.ufoCompiler import fetchCharacterMappingAndAnchors
from testSupport import getFontPath


def test_canReloadUFO(tmpdir):
    ufoSource = getFontPath("MutatorSansBoldWideMutated.ufo")
    ufoPath = shutil.copytree(ufoSource, tmpdir / "test.ufo")
    reader = UFOReader(ufoPath, validate=False)
    glyphSet = reader.getGlyphSet()
    cmap, unicodes, anchors = fetchCharacterMappingAndAnchors(glyphSet, ufoPath)

    state = UFOState(reader, glyphSet, getAnchors=lambda: anchors, getUnicodes=lambda: unicodes)
    canReload, needsInfoUpdate, newCmap = state.canReloadUFO()
    assert canReload
    assert not needsInfoUpdate
    assert newCmap is None

    feaPath = pathlib.Path(reader.fs.getsyspath("/features.fea"))
    feaPath.touch()
    canReload, needsInfoUpdate, newCmap = state.canReloadUFO()
    assert not canReload
    assert not needsInfoUpdate
    assert newCmap is None

    infoPath = pathlib.Path(reader.fs.getsyspath("/fontinfo.plist"))
    infoPath.touch()
    canReload, needsInfoUpdate, newCmap = state.canReloadUFO()
    assert canReload
    assert needsInfoUpdate
    assert newCmap is None

    glyphPath = pathlib.Path(glyphSet.fs.getsyspath(glyphSet.contents["A"]))
    glyph = Glyph("A", None)
    ppen = RecordingPointPen()
    glyphSet.readGlyph("A", glyph, ppen)
    glyph.anchors[0]["x"] = 123
    glyphSet.writeGlyph("A", glyph, ppen.replay)
    canReload, needsInfoUpdate, newCmap = state.canReloadUFO()
    assert not canReload

    cmap, unicodes, anchors = fetchCharacterMappingAndAnchors(glyphSet, ufoPath)
    state = UFOState(reader, glyphSet, getAnchors=lambda: anchors, getUnicodes=lambda: unicodes)
    glyph.unicodes = [123]
    glyphSet.writeGlyph("A", glyph, ppen.replay)
    canReload, needsInfoUpdate, newCmap = state.canReloadUFO()
    assert canReload
    assert not needsInfoUpdate
    assert newCmap is not None
    assert newCmap[123] == "A"
    assert ord("A") not in newCmap


def test_getUpdateInfo(tmpdir):
    ufoSource = getFontPath("MutatorSansBoldWideMutated.ufo")
    ufoPath = shutil.copytree(ufoSource, tmpdir / "test.ufo")
    reader = UFOReader(ufoPath, validate=False)
    glyphSet = reader.getGlyphSet()
    cmap, unicodes, anchors = fetchCharacterMappingAndAnchors(glyphSet, ufoPath)

    state1 = UFOState(reader, glyphSet, getAnchors=lambda: anchors, getUnicodes=lambda: unicodes)

    feaPath = pathlib.Path(reader.fs.getsyspath("/features.fea"))
    feaPath.touch()

    state2 = state1.newState()
    needsFeaturesUpdate, needsGlyphUpdate, needsInfoUpdate, needsCmapUpdate = state2.getUpdateInfo()
    assert needsFeaturesUpdate
    assert not needsGlyphUpdate
    assert not needsInfoUpdate
    assert not needsCmapUpdate

    infoPath = pathlib.Path(reader.fs.getsyspath("/fontinfo.plist"))
    infoPath.touch()

    state3 = state2.newState()
    needsFeaturesUpdate, needsGlyphUpdate, needsInfoUpdate, needsCmapUpdate = state3.getUpdateInfo()
    assert not needsFeaturesUpdate
    assert not needsGlyphUpdate
    assert needsInfoUpdate
    assert not needsCmapUpdate

    glyphPath = pathlib.Path(glyphSet.fs.getsyspath(glyphSet.contents["A"]))
    glyph = Glyph("A", None)
    ppen = RecordingPointPen()
    glyphSet.readGlyph("A", glyph, ppen)
    glyph.anchors[0]["x"] = 123
    glyphSet.writeGlyph("A", glyph, ppen.replay)

    state4 = state3.newState()
    needsFeaturesUpdate, needsGlyphUpdate, needsInfoUpdate, needsCmapUpdate = state4.getUpdateInfo()
    assert needsFeaturesUpdate
    assert needsGlyphUpdate
    assert not needsInfoUpdate
    assert not needsCmapUpdate

    glyphPath = pathlib.Path(glyphSet.fs.getsyspath(glyphSet.contents["A"]))
    glyph = Glyph("A", None)
    ppen = RecordingPointPen()
    glyphSet.readGlyph("A", glyph, ppen)
    glyph.unicodes = [123]
    glyphSet.writeGlyph("A", glyph, ppen.replay)

    state5 = state4.newState()
    needsFeaturesUpdate, needsGlyphUpdate, needsInfoUpdate, needsCmapUpdate = state5.getUpdateInfo()
    assert not needsFeaturesUpdate
    assert needsGlyphUpdate
    assert not needsInfoUpdate
    assert needsCmapUpdate
