from dataclasses import dataclass, field


@dataclass(frozen=True)
class TimingsRead:
    """`line_timings.json` on disk: state `none`, `ok` or `unreadable`; entries map an ordinal to (sha256, text).

    The text is the entry's line texts joined with one space (the sentence texts the align command stored).
    """

    state: str
    entries: dict[int, tuple[str, str]] = field(default_factory=dict)
