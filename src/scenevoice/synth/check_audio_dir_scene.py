import os
import stat
from pathlib import Path

from scenevoice.synth.audio_dir import AUDIO_DIR
from scenevoice.validation import Violation

_RULE = "out-audio"


def check_audio_dir_scene(out_dir: str | Path) -> Violation | None:
    """Scene mode: `DIR/audio` must already be a real directory. A missing path, a file and any
    symlink (even to a directory, even dangling) fail; `lstat` does not follow the link."""
    try:
        mode = os.lstat(os.path.join(out_dir, AUDIO_DIR)).st_mode
    except OSError:
        mode = 0
    if stat.S_ISDIR(mode):
        return None
    return Violation(_RULE, "--out/audio does not exist or is not a directory")
