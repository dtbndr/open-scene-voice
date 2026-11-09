import os
from pathlib import Path

from scenevoice.pack.manifest_name import MANIFEST_NAME
from scenevoice.pack.write_temp_file import write_temp_file


def write_manifest(directory: str | Path, data: bytes) -> str | None:
    """Write data unchanged as DIR/scene_manifest.csv via a same-directory temp file (never ending .csv), then atomic rename.

    The file gets the normal umask-derived mode before the rename, not mkstemp's 0600.
    Returns None on success, or a one-line message on failure; never raises OSError.
    """
    temp = None
    try:
        temp = write_temp_file(directory, data)
        os.replace(temp, os.path.join(directory, MANIFEST_NAME))
        return None
    except OSError:
        if temp is not None:
            try:
                os.remove(temp)
            except OSError:
                pass
        return f"could not write {MANIFEST_NAME}"
