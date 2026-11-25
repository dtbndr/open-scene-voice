from collections.abc import Mapping

from .timings_read import TimingsRead


def classify_line_markers(
    ordinals: tuple[int, ...], timings: TimingsRead, hashes: Mapping[int, str]
) -> tuple[str, tuple[int, ...]]:
    """`(state, stale ordinals)` of the line markers: `none`, `unreadable`, `fresh` or `stale`.

    Fresh means every plan ordinal has an entry whose sha256 equals the SHA-256 of that scene's WAV (as
    `pack/fresh_timings.py` defines it); a missing entry, a changed WAV or an unvoiced scene is stale.
    """
    if timings.state != "ok":
        return (timings.state, ())
    stale = tuple(
        ordinal for ordinal in ordinals
        if ordinal not in timings.entries or ordinal not in hashes or timings.entries[ordinal][0] != hashes[ordinal]
    )
    return ("stale" if stale else "fresh", stale)
