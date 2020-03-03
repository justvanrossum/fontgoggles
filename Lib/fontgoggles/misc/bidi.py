import itertools

# Monkeypatch bidi to use unicodedata2
import unicodedata2
import bidi.algorithm
bidi.algorithm.bidirectional = unicodedata2.bidirectional
bidi.algorithm.category = unicodedata2.category
bidi.algorithm.mirrored = unicodedata2.mirrored

from bidi.algorithm import (get_empty_storage, get_base_level, get_embedding_levels,
                            explicit_embed_and_overrides, resolve_weak_types,
                            resolve_neutral_types, resolve_implicit_levels,
                            reorder_resolved_levels, reorder_combining_marks, apply_mirroring,
                            PARAGRAPH_LEVELS)


def applyBiDi(text):
    """Apply the BiDi algorithm to the input text, and return the display
    string, and char index mappings for to_bidi and from_bidi.
    """
    storage, display = getBiDiInfo(text)
    run_lenghts = []
    for value, sub in itertools.groupby(storage['chars'], key=lambda ch: ch['level']):
        run_lenghts.append(len(list(sub)))
    assert sum(run_lenghts) == len(display)
    base_dir = storage['base_dir']
    from_bidi = [char_info['index'] for char_info in storage['chars']]
    to_bidi = [bidi_index for index, bidi_index in sorted(zip(from_bidi, range(len(text))))]
    return display, run_lenghts, base_dir, to_bidi, from_bidi


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
    reorder_combining_marks(storage, debug)
    apply_mirroring(storage, debug)

    chars = storage['chars']
    display = ''.join([_ch['ch'] for _ch in chars])
    return storage, display
