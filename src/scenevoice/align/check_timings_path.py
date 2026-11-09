import os
import stat
from pathlib import Path

from scenevoice.pack import TIMINGS_NAME


def check_timings_path(directory: str | Path) -> str | None:
    """Check 4 (timings part): None when DIR/line_timings.json is absent or a regular file, else a message.

    Uses os.lstat, so a symlink (even a dangling one) is refused; never raises OSError.
    """
    path = Path(directory) / TIMINGS_NAME
    try:
        mode = os.lstat(path).st_mode
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError as error:
        return f"{path}: cannot be checked ({error.strerror or 'os error'})"
    if not stat.S_ISREG(mode):
        return f"{path}: exists and is not a regular file"
    return None
