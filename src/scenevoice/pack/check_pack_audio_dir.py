import os
import stat
from pathlib import Path

from scenevoice.synth import AUDIO_DIR


def check_pack_audio_dir(directory: str | Path) -> str | None:
    """Check 2 (audio part): None when DIR/audio is a real directory, else a message.

    Uses os.lstat, so a symlink (even to a directory) is refused; never raises OSError.
    """
    path = Path(directory) / AUDIO_DIR
    try:
        mode = os.lstat(path).st_mode
    except (FileNotFoundError, NotADirectoryError):
        return f"{path}: directory does not exist"
    except OSError as error:
        return f"{path}: cannot be checked ({error.strerror or 'os error'})"
    if not stat.S_ISDIR(mode):
        return f"{path}: not a directory"
    return None
