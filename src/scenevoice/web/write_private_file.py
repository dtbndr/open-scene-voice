import os
import tempfile
from pathlib import Path


def write_private_file(directory: Path, prefix: str, suffix: str, data: bytes) -> Path:
    """Write `data` exactly to a new file in `directory` (`mkstemp`: exclusive, mode 0600) and return its absolute path."""
    descriptor, name = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
    except BaseException:
        os.unlink(name)
        raise
    return Path(name)
