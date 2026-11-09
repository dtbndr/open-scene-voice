from dataclasses import dataclass


@dataclass(frozen=True)
class LineTiming:
    """One sentence of a scene body and its start in ms (None when unmatched)."""

    text: str
    start_ms: int | None
