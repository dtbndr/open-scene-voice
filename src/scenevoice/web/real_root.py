import os
from pathlib import Path

from .key_file_overlap import key_file_overlap
from .workspace_error import KEY_FILE_MESSAGE, WorkspaceKeyFileError


def real_root(path: Path, key_file: Path | None = None) -> Path:
    """The workspace root with symlinks resolved: the one `realpath` step, never applied inside the root.

    A missing root is allowed and nothing is created. Raises when the resolved root holds the key file.
    """
    resolved = Path(os.path.realpath(path))
    if key_file is not None and key_file_overlap(resolved, os.path.realpath(key_file)):
        raise WorkspaceKeyFileError(KEY_FILE_MESSAGE)
    return resolved
