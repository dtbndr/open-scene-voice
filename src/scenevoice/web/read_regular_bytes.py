import os
import stat
from pathlib import Path

from .is_key_file import is_key_file
from .workspace_error import FileTooLargeError


def read_regular_bytes(path: Path, cap: int, key_file: Path | None = None) -> bytes | None:
    """The bytes of a regular, singly linked file that is not the key file, or None when refused.

    Opens without following a symlink and without blocking on a FIFO, checks the open descriptor, and reads at most
    `cap + 1` bytes: more than `cap` raises `FileTooLargeError`.
    """
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    try:
        fd = os.open(path, flags)
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or is_key_file(path, key_file, fd=fd):
            return None
        chunks: list[bytes] = []
        remaining = cap + 1
        while remaining > 0:
            chunk = os.read(fd, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    except OSError:
        return None
    finally:
        os.close(fd)
    data = b"".join(chunks)
    if len(data) > cap:
        raise FileTooLargeError(f"file holds more than {cap} bytes")
    return data
