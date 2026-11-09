from dataclasses import dataclass

from scenevoice.synth.alignment import Alignment


@dataclass(frozen=True)
class RecordEntry:
    """One scene's entry in synth_record.json (the seven contract fields)."""

    ordinal: int
    sha256: str
    voice: str
    model: str
    language: str | None
    instruction: str | None
    alignment: Alignment | None
