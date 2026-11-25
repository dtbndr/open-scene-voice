import os
import stat
from pathlib import Path

NOT_REGULAR = "not a regular file"


def regular_file_problem(path: str | Path) -> str | None:
    """Why `path` must not be opened as a file, or None. Only an existing non-regular target (FIFO, device,
    socket, directory) is a problem: a missing or dangling path, or any stat error, is left to the caller's
    own read error. Follows symlinks and never opens the path."""
    try:
        mode = os.stat(path).st_mode
    except (OSError, ValueError):
        return None
    return None if stat.S_ISREG(mode) else NOT_REGULAR
