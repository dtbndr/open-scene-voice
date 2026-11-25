import os
import stat
from pathlib import Path


def loose_permission_problem(path: str | Path) -> str | None:
    """Warning text when group or others can access `path` (POSIX only), else None.
    A stat error is left to the read error."""
    if os.name == "nt":
        return None
    try:
        mode = os.stat(path).st_mode
    except (OSError, ValueError):
        return None
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        return f"key file {path} can be read by other users; run chmod 600 {path}"
    return None
