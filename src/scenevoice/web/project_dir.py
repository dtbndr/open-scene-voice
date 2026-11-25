import os
import stat
from pathlib import Path

from .exact_entry import exact_entry
from .is_project_id import is_project_id


def project_dir(root: Path, project_id: str) -> Path | None:
    """The project folder under the already resolved `root`, or None.

    Refused before any filesystem call when the id is invalid; refused when it is not a byte-exact entry, or is a
    symlink, file or anything but a real directory.
    """
    if not is_project_id(project_id) or not exact_entry(root, project_id):
        return None
    path = root / project_id
    try:
        mode = os.lstat(path).st_mode
    except OSError:
        return None
    return path if stat.S_ISDIR(mode) else None
