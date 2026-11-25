from dataclasses import dataclass


@dataclass(frozen=True)
class RecordItem:
    """One scene's entry of `synth_record.json` as the web reads it; `characters` is the joined alignment or None."""

    ordinal: int
    sha256: str
    voice: str
    model: str
    language: str | None
    instruction: str | None
    characters: str | None
