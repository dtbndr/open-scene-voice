import os
import stat
from pathlib import Path

from scenevoice.synth.audio_dir import AUDIO_DIR
from scenevoice.validation import Violation

_RULE = "out-audio"


def check_audio_dir_full(out_dir: str | Path) -> Violation | None:
    """Full run: `DIR/audio` may be missing or a real directory; a file or any symlink fails."""
    try:
        mode = os.lstat(os.path.join(out_dir, AUDIO_DIR)).st_mode
    except OSError:
        return None
    if stat.S_ISDIR(mode):
        return None
    return Violation(_RULE, "--out/audio exists and is not a real directory")
