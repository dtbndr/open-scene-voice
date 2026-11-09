import os
import stat
from pathlib import Path

from scenevoice.synth.record_name import RECORD_NAME
from scenevoice.validation import Violation

_RULE = "record-path"


def check_record_path(out_dir: str | Path) -> Violation | None:
    """`DIR/synth_record.json` may be absent or a regular file; anything else (a directory, a symlink even
    to a regular file, a dangling symlink) is refused. Symlinks are not followed and the file is not opened."""
    try:
        mode = os.lstat(Path(out_dir) / RECORD_NAME).st_mode
    except FileNotFoundError:
        return None
    except OSError:
        return Violation(_RULE, f"could not check {RECORD_NAME}")
    if stat.S_ISREG(mode):
        return None
    return Violation(_RULE, f"{RECORD_NAME} exists and is not a regular file")
