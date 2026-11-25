import os
from pathlib import Path


def is_key_file(path: Path, key_file: Path | None, fd: int | None = None) -> bool:
    """True when `path` (or the open descriptor `fd`) is the key file; false when it cannot be told.

    The key file is never read, only compared by device and inode.
    """
    if key_file is None:
        return False
    try:
        if fd is None:
            return os.path.samefile(path, key_file)
        key = os.stat(key_file)
        opened = os.fstat(fd)
        return (opened.st_dev, opened.st_ino) == (key.st_dev, key.st_ino)
    except OSError:
        return False
