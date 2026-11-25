import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .copy_file import copy_file


@dataclass(frozen=True)
class FileOps:
    """The four filesystem moves Start again makes, as one value so a test can make any one of them fail."""

    rename: Callable[[Path, Path], None] = os.rename
    copy: Callable[[Path, Path], None] = copy_file
    replace: Callable[[Path, Path], None] = os.replace
    unlink: Callable[[Path], None] = os.unlink


REAL_OPS = FileOps()
