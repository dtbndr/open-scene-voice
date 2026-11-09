import os
from pathlib import Path

from scenevoice.pack.manifest_name import MANIFEST_NAME


def check_no_collision(directory: str | Path) -> str | None:
    """Check 3: None when nothing, not even a dangling symlink, sits at DIR/scene_manifest.csv."""
    try:
        os.lstat(Path(directory) / MANIFEST_NAME)
    except FileNotFoundError:
        return None
    except OSError as error:
        return f"{MANIFEST_NAME}: cannot be checked ({error.strerror or 'os error'})"
    return f"{MANIFEST_NAME} already exists in the directory"
