from dataclasses import dataclass


@dataclass(frozen=True)
class JobRead:
    """What a subscriber gets from one read of the buffer."""

    job: int
    events: tuple[dict[str, object], ...]
    ended: bool
    closed: bool
