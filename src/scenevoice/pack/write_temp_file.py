import os
import tempfile
from pathlib import Path


def _current_umask() -> int:
    mask = os.umask(0)
    try:
        return mask
    finally:
        os.umask(mask)


def write_temp_file(directory: str | Path, data: bytes) -> str:
    """Write data to a same-directory temp file (.write-*.tmp) with the umask-derived mode, and return its path.

    The caller renames it into place. On failure the temp file is removed and OSError is raised.
    """
    fd, temp = tempfile.mkstemp(prefix=".write-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(temp, 0o666 & ~_current_umask())
    except OSError:
        try:
            os.remove(temp)
        except OSError:
            pass
        raise
    return temp
