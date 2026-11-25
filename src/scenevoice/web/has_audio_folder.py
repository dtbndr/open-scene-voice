import os
import stat
from pathlib import Path

from .exact_entry import exact_entry


def has_audio_folder(directory: Path) -> bool:
    """True when `audio` is a byte-exact entry that is a real directory (never a symlink), as `synth --scene` requires."""
    if not exact_entry(directory, "audio"):
        return False
    try:
        return stat.S_ISDIR(os.lstat(directory / "audio").st_mode)
    except OSError:
        return False
