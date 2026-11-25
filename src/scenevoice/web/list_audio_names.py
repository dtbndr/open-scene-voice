import os
import stat
from pathlib import Path

from .audio_file_name import audio_file_name
from .exact_entry import exact_entry


def list_audio_names(directory: Path) -> list[str]:
    """Allowlisted `NNN.wav` names listed from the exact `audio` entry of `directory`, sorted.

    Only the one `audio` directory is listed (never a walk) and only when it is a real, byte-exact directory. Each
    name still has to pass `regular_file` before it is read.
    """
    if not exact_entry(directory, "audio"):
        return []
    path = directory / "audio"
    try:
        if not stat.S_ISDIR(os.lstat(path).st_mode):
            return []
        return sorted(name for name in os.listdir(path) if audio_file_name(name))
    except OSError:
        return []
