import os
from collections.abc import Iterable
from pathlib import Path

from scenevoice.synth.audio_rel_path import audio_rel_path


def find_collisions(out_dir: str | Path, ordinals: Iterable[int]) -> list[int]:
    """Ordinals whose `audio/NNN.wav` path already exists (lexists: dangling symlinks count)."""
    return [n for n in ordinals if os.path.lexists(os.path.join(out_dir, audio_rel_path(n)))]
