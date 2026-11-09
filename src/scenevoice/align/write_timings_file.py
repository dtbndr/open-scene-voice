import os
from pathlib import Path

from scenevoice.pack import TIMINGS_NAME, write_temp_file


def write_timings_file(directory: str | Path, data: bytes) -> str | None:
    """Write data unchanged as DIR/line_timings.json via a same-directory temp file (never ending .json), then atomic rename.

    Returns None on success, or a one-line message on failure; never raises OSError.
    An existing line_timings.json is untouched on failure.
    """
    temp = None
    try:
        temp = write_temp_file(directory, data)
        os.replace(temp, os.path.join(directory, TIMINGS_NAME))
        return None
    except OSError:
        if temp is not None:
            try:
                os.remove(temp)
            except OSError:
                pass
        return f"could not write {TIMINGS_NAME}"
