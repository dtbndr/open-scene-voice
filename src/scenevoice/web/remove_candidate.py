import os
from pathlib import Path


def remove_candidate(candidate: Path) -> None:
    """Unlink the candidate name: a symlink loses only the link, a directory or a missing name is left, nothing raises."""
    try:
        os.unlink(candidate)
    except OSError:
        pass
