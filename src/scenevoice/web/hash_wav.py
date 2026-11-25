import hashlib
import os
from pathlib import Path

from .open_regular_file import open_regular_file
from .workspace_error import FileTooLargeError

CHUNK = 1024 * 1024
AUDIO_CAP = 256 * 1024 * 1024


def hash_wav(path: Path, key_file: Path | None, cap: int = AUDIO_CAP) -> str | None:
    """SHA-256 hex of a plain WAV read once in 1 MiB chunks, or None when refused, over `cap` or unreadable."""
    try:
        opened = open_regular_file(path, cap, key_file)
    except FileTooLargeError:
        return None
    if opened is None:
        return None
    fd, size = opened
    digest = hashlib.sha256()
    try:
        remaining = size
        while remaining > 0:
            chunk = os.read(fd, min(CHUNK, remaining))
            if not chunk:
                break
            digest.update(chunk)
            remaining -= len(chunk)
    except OSError:
        return None
    finally:
        os.close(fd)
    return digest.hexdigest()
