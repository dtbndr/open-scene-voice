import os
import re
import stat
from pathlib import Path

_BACKUP = re.compile(r"\.write-restart-[0-9a-f]+-.+\.tmp")


def _holds_backup(folder: Path) -> bool:
    try:
        names = os.listdir(folder)
    except OSError:
        return False
    for name in names:
        if _BACKUP.fullmatch(name) is None:
            continue
        try:
            if stat.S_ISREG(os.lstat(folder / name).st_mode):  # lstat only: the file is never opened
                return True
        except OSError:
            continue
    return False


def scan_backups(directory: Path) -> bool:
    """True when an exact `.write-restart-<hex>-<name>.tmp` regular file sits in the project folder or its `audio/`.

    A directory listing plus `lstat`, never an open; a symlinked or missing `audio/` is not listed.
    """
    audio = directory / "audio"
    try:
        real_audio = stat.S_ISDIR(os.lstat(audio).st_mode)
    except OSError:
        real_audio = False
    return _holds_backup(directory) or (real_audio and _holds_backup(audio))
