import os
from pathlib import Path

from scenevoice.validation import Violation

_RULE = "out-dir"


def check_out_dir_exists(path: str | Path) -> Violation | None:
    """Scene mode: `--out` must already be a directory. A missing path, a regular file and a
    dangling symlink all fail; nothing is created."""
    if os.path.isdir(path):
        return None
    return Violation(_RULE, "--out does not exist or is not a directory")
