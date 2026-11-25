import os
import re
import tempfile
from pathlib import Path

from .exact_entry import exact_entry
from .is_key_file import is_key_file
from .workspace_error import WorkspaceError

_PLAIN_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")


def _read_umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask


_UMASK = _read_umask()  # once, at import: the set-and-restore round trip is not thread safe per request


def write_file_atomic(directory: Path, name: str, data: bytes, key_file: Path | None = None) -> None:
    """Replace `directory/name` with exactly `data` through a same-directory `.write-*.tmp` file.

    The mode is the umask-derived one. Refuses (raises `WorkspaceError`) when the target is the key file or has more
    than one hard link; a failed write leaves the old file and no temp file. `name` must be a plain constant.
    """
    if _PLAIN_NAME.fullmatch(name) is None:
        raise ValueError(f"not a plain file name: {name!r}")
    target = directory / name
    if exact_entry(directory, name):
        if is_key_file(target, key_file):
            raise WorkspaceError("That file is your key file; SceneVoice will not write over it.")
        if os.lstat(target).st_nlink > 1:
            raise WorkspaceError("That file has more than one hard link; SceneVoice will not write over it.")
    fd, temp = tempfile.mkstemp(prefix=".write-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.chmod(temp, 0o666 & ~_UMASK)
        os.replace(temp, target)
    except BaseException:
        try:
            os.remove(temp)
        except OSError:
            pass
        raise
