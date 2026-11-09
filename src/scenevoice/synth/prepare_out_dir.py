import os
from pathlib import Path

from scenevoice.synth.probe_out_dir import probe_out_dir
from scenevoice.validation import Violation

_RULE = "out-dir"


def prepare_out_dir(path: str | Path) -> Violation | None:
    """Step 6: create with parents, then prove writability with a probe file that is removed."""
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return Violation(_RULE, "could not create the output directory")
    return probe_out_dir(path)
