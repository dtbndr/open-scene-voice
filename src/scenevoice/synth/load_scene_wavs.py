import os
import stat
from pathlib import Path

from scenevoice.synth.audio_rel_path import audio_rel_path
from scenevoice.synth.plan_scene import PlanScene
from scenevoice.synth.read_wav_frames import read_wav_frames
from scenevoice.synth.scene_wav import SceneWav


def _read(path: Path) -> bytes | str:
    """The file's bytes, or a reason (str). Never raises."""
    try:
        if not stat.S_ISREG(os.lstat(path).st_mode):
            return "missing or not a regular file"
        return path.read_bytes()
    except OSError:
        return "missing or not a regular file" if not path.exists() else "cannot be read"


def load_scene_wavs(
    scenes: list[PlanScene], directory: str | Path, min_frames: int
) -> list[SceneWav] | str:
    """Validated bytes and frame count per scene in plan order, or a one-line message for the first failure.

    Each file is read once. min_frames is the zero-frame rule: a valid WAV with fewer frames fails (0 turns it off).
    """
    loaded: list[SceneWav] = []
    for scene in scenes:
        name = audio_rel_path(scene.ordinal)
        data = _read(Path(directory) / name)
        frames = data if isinstance(data, str) else read_wav_frames(data)
        if isinstance(frames, str):
            return f"scene {scene.ordinal}: {name}: {frames}"
        if frames < min_frames:
            return f"scene {scene.ordinal}: {name}: fewer than {min_frames} frames, too short for a timeline clip"
        assert isinstance(data, bytes)
        loaded.append(SceneWav(data, frames))
    return loaded
