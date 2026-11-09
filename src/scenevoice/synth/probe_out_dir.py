import os
import tempfile
from pathlib import Path

from scenevoice.validation import Violation

_RULE = "out-dir"


def probe_out_dir(path: str | Path) -> Violation | None:
    """Prove writability with a probe file that is removed. Creates nothing else."""
    try:
        fd, probe = tempfile.mkstemp(prefix=".probe-", suffix=".tmp", dir=path)
    except OSError:
        return Violation(_RULE, "output directory is not writable")
    try:
        os.close(fd)
        os.remove(probe)
    except OSError:
        return Violation(_RULE, "output directory is not writable")
    return None
