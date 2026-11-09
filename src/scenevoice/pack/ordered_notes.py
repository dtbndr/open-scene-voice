from scenevoice.pack.skipped_marker_note import skipped_marker_note
from scenevoice.pack.timings_freshness import TimingsFreshness
from scenevoice.pack.timings_notes import MISSING_FILE_NOTE, timings_notes


def ordered_notes(
    freshness: TimingsFreshness, missing_file: bool, skipped: list[tuple[int, int]]
) -> list[str]:
    """All NOTE lines: the missing-file note, then per scene in plan order a stale or missing-entry note, then its skipped lines."""
    notes = [MISSING_FILE_NOTE] if missing_file else []
    # (ordinal, 0) sorts before that scene's skipped lines (ordinal, line >= 1): stale or missing scenes have no skipped lines; plan ordinals are 1..N in plan order.
    keyed: list[tuple[int, int, str]] = []
    for pair, note in zip(freshness.unusable, timings_notes(freshness), strict=True):
        keyed.append((pair[0], 0, note))
    for ordinal, line in skipped:
        keyed.append((ordinal, line, skipped_marker_note(ordinal, line)))
    keyed.sort(key=lambda item: item[:2])
    return notes + [note for _, _, note in keyed]
