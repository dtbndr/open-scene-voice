import os
import stat
from pathlib import Path

from scenevoice.synth.audio_dir import AUDIO_DIR
from scenevoice.synth.wav_name import wav_name
from scenevoice.validation import Violation

_RULE = "scene-target"


def check_scene_target(out_dir: str | Path, scene: int) -> Violation | None:
    """Scene mode: the target `DIR/audio/NNN.wav` (`out_dir` is DIR) may be absent or a regular file. Anything else (a
    directory, a symlink even to a regular file, a dangling symlink) is refused. Symlinks are
    not followed, since `os.replace` would replace the link itself."""
    name = wav_name(scene)
    try:
        mode = os.lstat(Path(out_dir) / AUDIO_DIR / name).st_mode
    except FileNotFoundError:
        return None
    except OSError:
        return Violation(_RULE, f"could not check {name}")
    if stat.S_ISREG(mode):
        return None
    return Violation(_RULE, f"{name} exists and is not a regular file")
