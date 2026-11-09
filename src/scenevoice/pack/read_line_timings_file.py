import os
import stat
from pathlib import Path

from scenevoice.pack.timings_name import TIMINGS_NAME


def read_line_timings_file(directory: str | Path) -> bytes | str | None:
    """None when DIR/line_timings.json is absent, its bytes when a regular file, else a message.

    Uses os.lstat, so a symlink (even a dangling one) is refused; never raises.
    """
    path = Path(directory) / TIMINGS_NAME
    try:
        mode = os.lstat(path).st_mode
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError as error:
        return f"{path}: cannot be checked ({error.strerror or 'os error'})"
    if not stat.S_ISREG(mode):
        return f"{path}: not a regular file"
    try:
        return path.read_bytes()
    except OSError as error:
        return f"{path}: cannot be read ({error.strerror or 'os error'})"
