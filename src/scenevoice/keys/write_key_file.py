import os
import tempfile
from collections.abc import Mapping
from pathlib import Path

from scenevoice.keys.render_key_file import render_key_file
from scenevoice.validation import Violation


def write_key_file(path: str | Path, values: Mapping[str, str]) -> Violation | None:
    """Write the key file atomically: a 0600 temp file in the same directory, then `os.replace`.
    A new parent directory is created 0700; an existing one is left as it is.
    Messages carry the path only, never a value."""
    final = Path(path)
    temp_name: str | None = None
    try:
        os.makedirs(final.parent, mode=0o700, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(dir=final.parent, prefix=".keys-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(render_key_file(values))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, final)
        temp_name = None
        return None
    except OSError:
        return Violation("key-file", f"could not write key file {path}")
    finally:
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
