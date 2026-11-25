from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BeatsStart:
    """What `begin_beats` made ready: the candidate path, the counted script bytes for the child's private copy, and the end hook."""

    candidate: Path
    script: bytes
    hook: Callable[[str, int], tuple[str | None, str | None]]
