from dataclasses import dataclass

from scenevoice.pack import LineTiming


@dataclass(frozen=True)
class SceneTimings:
    """One scene's entry in line_timings.json: ordinal, WAV hash and lines."""

    ordinal: int
    sha256: str
    lines: list[LineTiming]
