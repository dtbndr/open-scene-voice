from dataclasses import dataclass


@dataclass(frozen=True)
class SceneWav:
    """One validated scene WAV: its exact bytes and frame count."""

    data: bytes
    frames: int
