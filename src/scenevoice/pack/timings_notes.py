from scenevoice.pack.timings_freshness import TimingsFreshness

MISSING_FILE_NOTE = "scenevoice pack: NOTE no line_timings.json, scene markers only"


def timings_notes(freshness: TimingsFreshness) -> list[str]:
    """One NOTE per stale or missing scene, in plan order."""
    notes = []
    for ordinal, reason in freshness.unusable:
        what = "line timings stale" if reason == "stale" else "no line timings entry"
        notes.append(f"scenevoice pack: NOTE scene {ordinal}: {what}, scene marker only")
    return notes
