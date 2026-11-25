import os
import stat
from pathlib import Path

from scenevoice.beats.path_exists_message import path_exists_message

_SEPARATORS = tuple({"/", os.sep, os.altsep or "/"})


def _cannot_be_checked(path: object, error: OSError) -> str:
    return f"{path} cannot be checked ({error.strerror or 'os error'})"


def check_out_path(path: str | Path, *, command: str) -> str | None:
    """None when nothing (not even a dangling symlink) sits at path and its parent is a writable directory.

    Returns a one-line message otherwise; never raises OSError. A string that is blank or ends
    in a separator names no file (Path would silently drop the slash), so it is refused here.
    """
    if isinstance(path, str) and (not path.strip() or path.endswith(_SEPARATORS)):
        return f"--out {path!r} has no file name; give a path that ends in a file name"
    try:
        os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        pass
    except OSError as error:
        return _cannot_be_checked(path, error)
    else:
        return path_exists_message(path, command=command)
    parent = Path(path).parent
    try:
        parent_mode = os.stat(parent).st_mode
    except (FileNotFoundError, NotADirectoryError):
        return f"{parent} is not an existing directory"
    except OSError as error:
        return _cannot_be_checked(parent, error)
    if not stat.S_ISDIR(parent_mode):
        return f"{parent} is not an existing directory"
    if not os.access(parent, os.W_OK | os.X_OK):
        return f"{parent} is not a writable directory"
    return None
