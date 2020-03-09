import itertools
from fontTools.unicodedata import script
from unicodedata2 import category

# Monkeypatch bidi to use unicodedata2
import unicodedata2
import bidi.algorithm
bidi.algorithm.bidirectional = unicodedata2.bidirectional
bidi.algorithm.category = unicodedata2.category
bidi.algorithm.mirrored = unicodedata2.mirrored
from bidi.algorithm import (get_empty_storage, get_base_level, get_embedding_levels,
                            explicit_embed_and_overrides, resolve_weak_types,
                            resolve_neutral_types, resolve_implicit_levels,
                            reorder_resolved_levels, PARAGRAPH_LEVELS)
from bidi.mirror import MIRRORED


UNKNOWN_SCRIPT = {"Zinh", "Zyyy", "Zxxx"}


def textSegments(txt):
    scripts = detectScript(txt)
    storage = getBiDiInfo(txt)

    levels = [None] * len(txt)
    for ch in storage['chars']:
        levels[ch['index']] = ch['level']

    prevLevel = storage['base_level']
    for i, level in enumerate(levels):
        if level is None:
            levels[i] = prevLevel
        else:
            prevLevel = level

    chars = list(zip(txt, scripts, levels))

    runLenghts = []
    for value, sub in itertools.groupby(chars, key=lambda item: item[1:]):
        runLenghts.append(len(list(sub)))

    segments = []
    index = 0
    for rl in runLenghts:
        nextIndex = index + rl
        segment = chars[index:nextIndex]
        runChars = "".join(ch for ch, script, bidiLevel in segment)
        _, script, bidiLevel = segment[0]
        segments.append((runChars, script, bidiLevel, index))
        index = nextIndex
    return segments, storage['base_level']


def detectScript(txt):
    charScript = [script(c) for c in txt]

    for i, ch in enumerate(txt):
        scr = charScript[i]
        if scr in UNKNOWN_SCRIPT:
            if i:
                scr = charScript[i-1]
            else:
                scr = None
            cat = category(ch)
            if ch in MIRRORED and cat == "Pe":
                scr = None
        charScript[i] = scr

    # Any unknowns should be mapped to the _next_ script
    prev = None
    for i in range(len(txt) - 1, -1, -1):
        if charScript[i] is None:
            charScript[i] = prev
        else:
            prev = charScript[i]

    # There may be unknowns at the end of the string, fall back to
    # preceding script
    prev = "Zxxx"  # last resort
    for i in range(len(txt)):
        if charScript[i] is None:
            charScript[i] = prev
        else:
            prev = charScript[i]

    assert None not in charScript

    return charScript


# copied from bidi/algorthm.py and modified to be more useful for us.

def getBiDiInfo(text, *, upper_is_rtl=False, base_dir=None, debug=False):
    """
    Set `upper_is_rtl` to True to treat upper case chars as strong 'R'
    for debugging (default: False).

    Set `base_dir` to 'L' or 'R' to override the calculated base_level.

    Set `debug` to True to display (using sys.stderr) the steps taken with the
    algorithm.

    Returns an info dict object and the display layout.
    """
    storage = get_empty_storage()

    if base_dir is None:
        base_level = get_base_level(text, upper_is_rtl)
    else:
        base_level = PARAGRAPH_LEVELS[base_dir]

    storage['base_level'] = base_level
    storage['base_dir'] = ('L', 'R')[base_level]

    get_embedding_levels(text, storage, upper_is_rtl, debug)
    assert len(text) == len(storage["chars"])
    for index, (ch, chInfo) in enumerate(zip(text, storage["chars"])):
        assert ch == chInfo["ch"]
        chInfo["index"] = index

    explicit_embed_and_overrides(storage, debug)
    resolve_weak_types(storage, debug)
    resolve_neutral_types(storage, debug)
    resolve_implicit_levels(storage, debug)
    reorder_resolved_levels(storage, debug)

    return storage
