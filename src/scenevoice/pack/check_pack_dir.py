import os
import stat
from pathlib import Path


def check_pack_dir(directory: str | Path) -> str | None:
    """Check 2: None when DIR is an existing directory (a symlink to one is fine), else a message.

    Uses os.stat (follows symlinks); never raises OSError.
    """
    path = Path(directory)
    try:
        mode = os.stat(path).st_mode
    except (FileNotFoundError, NotADirectoryError):
        return f"{path}: directory does not exist"
    except OSError as error:
        return f"{path}: cannot be checked ({error.strerror or 'os error'})"
    if not stat.S_ISDIR(mode):
        return f"{path}: not a directory"
    return None
