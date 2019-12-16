from bidi.algorithm import (get_empty_storage, get_base_level, get_embedding_levels,
                            explicit_embed_and_overrides, resolve_weak_types,
                            resolve_neutral_types, resolve_implicit_levels,
                            reorder_resolved_levels, apply_mirroring,
                            PARAGRAPH_LEVELS)


# copied from bidi/algorthm.py and modified to be more useful for us.

def getBidiInfo(text, *, upper_is_rtl=False, base_dir=None, debug=False):
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
    apply_mirroring(storage, debug)

    chars = storage['chars']
    display = ''.join([_ch['ch'] for _ch in chars])
    return storage, display
