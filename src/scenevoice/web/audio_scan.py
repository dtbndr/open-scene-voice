from dataclasses import dataclass, field


@dataclass(frozen=True)
class AudioScan:
    """`audio/` on disk: every ordinal named like a synth WAV, and the SHA-256 of each plain, readable one (voiced). `folder` defaults to True so a hand-built scan means a present folder."""

    named: tuple[int, ...] = ()
    hashes: dict[int, str] = field(default_factory=dict)
    folder: bool = field(default=True, compare=False)  # `audio/` is a real directory; a fact beside the names, not part of them
