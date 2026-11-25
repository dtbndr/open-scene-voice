from dataclasses import dataclass


@dataclass(frozen=True)
class JobLatest:
    """The newest job the buffer knows: its number (0 for none), whether it is still open, its `end` seq (0 if open)."""

    number: int
    live: bool
    end_seq: int
