import os
from pathlib import Path

from scenevoice.validation import Violation

_RULE = "out-path"


def check_out_path(path: str | Path) -> Violation | None:
    """Step 5: a path that resolves to a non-directory fails. A dangling symlink resolves to
    nothing, so it passes here and fails later, at step 6."""
    if os.path.exists(path) and not os.path.isdir(path):
        return Violation(_RULE, "--out exists and is not a directory")
    return None
