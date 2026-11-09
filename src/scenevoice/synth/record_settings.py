from dataclasses import dataclass


@dataclass(frozen=True)
class RecordSettings:
    """The settings a record entry is written under."""

    voice: str
    model: str
    language: str | None
    instruction: str | None
