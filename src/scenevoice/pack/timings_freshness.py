from dataclasses import dataclass, field

from scenevoice.pack.line_timing import LineTiming


@dataclass(frozen=True)
class TimingsFreshness:
    """Per plan scene: fresh lines by ordinal, and (ordinal, "stale"|"missing") otherwise."""

    fresh: dict[int, list[LineTiming]] = field(default_factory=dict)
    unusable: list[tuple[int, str]] = field(default_factory=list)
