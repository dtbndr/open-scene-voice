import json
from collections.abc import Sequence

from scenevoice.synth.record_entry import RecordEntry


def serialize_record(entries: Sequence[RecordEntry]) -> bytes:
    """Return the exact bytes of synth_record.json: indent 2, raw non-ASCII, one LF."""
    document = {
        "scenes": [
            {
                "ordinal": entry.ordinal,
                "sha256": entry.sha256,
                "voice": entry.voice,
                "model": entry.model,
                "language": entry.language,
                "instruction": entry.instruction,
                "alignment": None
                if entry.alignment is None
                else {
                    "characters": list(entry.alignment.characters),
                    "character_start_times_seconds": list(
                        entry.alignment.character_start_times_seconds
                    ),
                    "character_end_times_seconds": list(
                        entry.alignment.character_end_times_seconds
                    ),
                },
            }
            for entry in entries
        ]
    }
    text = json.dumps(document, indent=2, ensure_ascii=False)
    return (text + "\n").encode("utf-8")
