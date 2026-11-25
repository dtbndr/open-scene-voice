import os
import stat
from pathlib import Path

from .exact_entry import exact_entry
from .is_key_file import is_key_file


def regular_file(directory: Path, *parts: str, key_file: Path | None = None) -> Path | None:
    """The path of a regular, singly linked file reached through real directories below `directory`, or None.

    Every part must be a byte-exact entry; intermediate parts must be real directories, the last a regular file with
    one hard link that is not the key file. Symlinks are never followed.
    """
    current = directory
    for index, part in enumerate(parts):
        if not exact_entry(current, part):
            return None
        current = current / part
        try:
            info = os.lstat(current)
        except OSError:
            return None
        if index < len(parts) - 1:
            if not stat.S_ISDIR(info.st_mode):
                return None
        elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            return None
    if current == directory or is_key_file(current, key_file):
        return None
    return current
