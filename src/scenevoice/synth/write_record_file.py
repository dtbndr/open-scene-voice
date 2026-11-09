import os
import tempfile
from pathlib import Path

from scenevoice.synth.record_name import RECORD_NAME


def _current_umask() -> int:
    mask = os.umask(0)
    try:
        return mask
    finally:
        os.umask(mask)


def write_record_file(directory: str | Path, data: bytes) -> str | None:
    """Write the record bytes as synth_record.json via a same-directory temp file (never ending .json), then atomic rename.

    The file gets the normal umask-derived mode before the rename, not mkstemp's 0600.
    Returns None on success or the failure message; never raises OSError.
    """
    temp = None
    try:
        fd, temp = tempfile.mkstemp(prefix=".write-", suffix=".tmp", dir=directory)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(temp, 0o666 & ~_current_umask())
        os.replace(temp, os.path.join(directory, RECORD_NAME))
        return None
    except OSError:
        if temp is not None:
            try:
                os.remove(temp)
            except OSError:
                pass
        return f"could not write {RECORD_NAME}"
