import shutil
from pathlib import Path


def remove_launch_dir(path: Path) -> None:
    """Delete a launch directory; an already-missing directory is fine."""
    shutil.rmtree(path, ignore_errors=True)
