from scenevoice.synth.one_line import one_line
from scenevoice.synth.record_entry import RecordEntry
from scenevoice.synth.record_settings import RecordSettings


def _shown(value: str | None) -> str:
    return "(none)" if value is None else f'"{one_line(value)}"'


def settings_mismatch(
    ordinal: int, entry: RecordEntry, passed: RecordSettings
) -> str | None:
    """Return the pinned mismatch text (no prefix), or None when all four match."""
    pairs = (
        ("voice", entry.voice, passed.voice),
        ("model", entry.model, passed.model),
        ("language", entry.language, passed.language),
        ("instruction", entry.instruction, passed.instruction),
    )
    parts = [
        f"{name} recorded {_shown(recorded)}, passed {_shown(given)}"
        for name, recorded, given in pairs
        if recorded != given
    ]
    if not parts:
        return None
    head = f"scene {ordinal} settings differ from synth_record.json: "
    return head + "; ".join(parts)
