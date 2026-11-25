import os
import re
import stat
from pathlib import Path

_CANDIDATE = re.compile(r"\.write-beats-[0-9a-f]+\.tmp")


def sweep_candidates(directory: Path) -> None:
    """Delete leftover beats candidates: exact regular `.write-beats-<hex>.tmp` files in the project folder, nothing else.

    A hard kill (or a cancelled run) can leave one behind. Names are matched exactly and each is `lstat`ed, never
    followed: a symlink or directory with the name stays. The Start again backups and restore temps
    (`.write-restart-*`, `.write-restore-*`), every other `.write-*.tmp` and `audio/` are not looked at. A file that
    cannot be removed is left (the next start tries again).
    """
    for name in os.listdir(directory):
        if _CANDIDATE.fullmatch(name) is None:
            continue
        path = directory / name
        try:
            if stat.S_ISREG(os.lstat(path).st_mode):
                os.unlink(path)
        except OSError:
            continue
