from dataclasses import dataclass


@dataclass(frozen=True)
class StdoutCapture:
    """The first bytes of a child's standard output and the full byte count that was written."""

    data: bytes
    total: int
