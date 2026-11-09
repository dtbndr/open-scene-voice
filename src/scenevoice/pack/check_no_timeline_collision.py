import os
from pathlib import Path

from scenevoice.pack.timeline_name import TIMELINE_NAME


def check_no_timeline_collision(directory: str | Path) -> str | None:
    """Check 3a (editor runs): None when nothing, not even a dangling symlink, sits at DIR/resolve_timeline.otio."""
    try:
        os.lstat(Path(directory) / TIMELINE_NAME)
    except FileNotFoundError:
        return None
    except OSError as error:
        return f"{TIMELINE_NAME}: cannot be checked ({error.strerror or 'os error'})"
    return f"{TIMELINE_NAME} already exists in the directory"
