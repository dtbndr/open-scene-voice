import os
import stat
from pathlib import Path

from .is_key_file import is_key_file
from .workspace_error import FileTooLargeError


def open_regular_file(path: Path, cap: int, key_file: Path | None = None) -> tuple[int, int] | None:
    """`(descriptor, size)` of a regular, singly linked file that is not the key file, or None when refused.

    Opens without following a symlink and without blocking on a FIFO, and checks the open descriptor. A size over
    `cap` raises `FileTooLargeError` before any read. The caller closes the descriptor.
    """
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    try:
        fd = os.open(path, flags)
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or is_key_file(path, key_file, fd=fd):
            os.close(fd)
            return None
        if info.st_size > cap:
            os.close(fd)
            raise FileTooLargeError(f"file holds more than {cap} bytes")
    except OSError:
        os.close(fd)
        return None
    return fd, info.st_size
