import asyncio
import os
import pytest
from fontTools.ufoLib import UFOReader
from fontgoggles.misc.ufoCompiler import fetchCharacterMappingAndAnchors
from fontgoggles.misc.ufoCompilerPool import compileUFOToPath, _resetPool
from testSupport import getFontPath


def test_ufoCharacterMapping():
    ufoPath = getFontPath("MutatorSansBoldWideMutated.ufo")
    reader = UFOReader(ufoPath)
    cmap, revCmap, anchors = fetchCharacterMappingAndAnchors(reader.getGlyphSet(), ufoPath)
    assert cmap[0x0041] == "A"
    assert revCmap["A"] == [0x0041]
    # MutatorSansBoldWideMutated.ufo/glyphs/A_.glif contains a commented-out <unicode>
    # tag, that must not be parsed, as well as a commented-out <anchor>.
    assert 0x1234 not in cmap
    assert anchors == {"A": [("top", 645, 815)], "E": [("top", 582.5, 815)], "macroncmb": [("_top", 0, 815)]}


@pytest.mark.asyncio
async def test_ufoCompilerPool(tmpdir):
    _resetPool()
    ufoPath = getFontPath("MutatorSansBoldWideMutated.ufo")
    ttPath = tmpdir / "test.ttf"
    output, error = await compileUFOToPath(ufoPath, ttPath)
    assert ttPath.exists()
    assert os.stat(ttPath).st_size > 0
    assert not error
    assert output == ""


@pytest.mark.asyncio
async def test_compileMultiple(tmpdir):
    _resetPool()
    ufoPaths = [
        getFontPath("MutatorSansBoldCondensed.ufo"),
        getFontPath("MutatorSansBoldWide.ufo"),
        getFontPath("MutatorSansIntermediateCondensed.ufo"),
        getFontPath("MutatorSansIntermediateWide.ufo"),
        getFontPath("MutatorSansLightCondensed.ufo"),
        getFontPath("MutatorSansLightCondensed_support.S.middle.ufo"),
        getFontPath("MutatorSansLightCondensed_support.S.wide.ufo"),
        getFontPath("MutatorSansLightCondensed_support.crossbar.ufo"),
        getFontPath("MutatorSansLightWide.ufo"),
    ]
    ttPaths = [tmpdir / (u.name + ".ttf") for u in ufoPaths]
    coros = (compileUFOToPath(u, t) for u, t in zip(ufoPaths, ttPaths))
    results = await asyncio.gather(*coros)
    assert len(results) == len(ufoPaths)
    assert [error for p, error in results] == [False] * len(results)
    assert [(os.stat(p).st_size > 0) for p in ttPaths] == [True] * len(results)
