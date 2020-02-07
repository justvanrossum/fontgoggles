import pathlib
import shutil
from fontTools.pens.recordingPen import RecordingPointPen
from fontTools.ufoLib import UFOReader
from fontTools.ufoLib.glifLib import Glyph
from fontgoggles.font.ufoFont import UFOState
from fontgoggles.compile.ufoCompiler import fetchCharacterMappingAndAnchors
from testSupport import getFontPath


def test_changedGlyphs(tmpdir):
    ufoSource = getFontPath("MutatorSansBoldWideMutated.ufo")
    ufoPath = shutil.copytree(ufoSource, tmpdir / "test.ufo")
    reader = UFOReader(ufoPath, validate=False)
    glyphSet = reader.getGlyphSet()
    cmap, unicodes, anchors = fetchCharacterMappingAndAnchors(glyphSet, ufoPath)

    stateBefore = UFOState(reader, glyphSet, getAnchors=lambda: anchors, getUnicodes=lambda: unicodes)
    canReload, needsInfoUpdate, newCmap = stateBefore.canReloadUFO()
    assert canReload
    assert not needsInfoUpdate
    assert newCmap is None

    feaPath = pathlib.Path(reader.fs.getsyspath("/features.fea"))
    feaPath.touch()
    canReload, needsInfoUpdate, newCmap = stateBefore.canReloadUFO()
    assert not canReload
    assert not needsInfoUpdate
    assert newCmap is None

    infoPath = pathlib.Path(reader.fs.getsyspath("/fontinfo.plist"))
    infoPath.touch()
    canReload, needsInfoUpdate, newCmap = stateBefore.canReloadUFO()
    assert canReload
    assert needsInfoUpdate
    assert newCmap is None

    glyphPath = pathlib.Path(glyphSet.fs.getsyspath(glyphSet.contents["A"]))
    glyph = Glyph("A", None)
    ppen = RecordingPointPen()
    glyphSet.readGlyph("A", glyph, ppen)
    glyph.anchors[0]["x"] = 123
    glyphSet.writeGlyph("A", glyph, ppen.replay)
    canReload, needsInfoUpdate, newCmap = stateBefore.canReloadUFO()
    assert not canReload

    cmap, unicodes, anchors = fetchCharacterMappingAndAnchors(glyphSet, ufoPath)
    stateBefore = UFOState(reader, glyphSet, getAnchors=lambda: anchors, getUnicodes=lambda: unicodes)
    glyph.unicodes = [123]
    glyphSet.writeGlyph("A", glyph, ppen.replay)
    canReload, needsInfoUpdate, newCmap = stateBefore.canReloadUFO()
    assert canReload
    assert not needsInfoUpdate
    assert newCmap is not None
    assert newCmap[123] == "A"
    assert ord("A") not in newCmap
