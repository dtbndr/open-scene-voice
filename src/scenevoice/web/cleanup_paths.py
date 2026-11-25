import shutil
from collections.abc import Iterable
from pathlib import Path


def cleanup_paths(paths: Iterable[Path]) -> None:
    """Delete files and directories; a missing path or a failed delete never raises."""
    for path in paths:
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
        except OSError:
            continue
