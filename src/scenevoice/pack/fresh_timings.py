import hashlib

from scenevoice.pack.line_timing import LineTiming
from scenevoice.pack.timings_freshness import TimingsFreshness


def fresh_timings(
    table: dict[int, tuple[str, list[LineTiming]]], held: list[tuple[int, bytes]]
) -> TimingsFreshness:
    """Decide per plan scene (ordinal, held WAV bytes), in plan order: fresh, stale or missing.

    Fresh means the entry's sha256 equals the SHA-256 of the held bytes.
    """
    fresh: dict[int, list[LineTiming]] = {}
    unusable: list[tuple[int, str]] = []
    for ordinal, data in held:
        entry = table.get(ordinal)
        if entry is None:
            unusable.append((ordinal, "missing"))
        elif entry[0] == hashlib.sha256(data).hexdigest():
            fresh[ordinal] = entry[1]
        else:
            unusable.append((ordinal, "stale"))
    return TimingsFreshness(fresh, unusable)
