import os
import stat
from pathlib import Path

from .not_ordinary import NotOrdinary
from .pack_output_names import pack_output_names
from .restart_names import restart_names


def _is_key(status: os.stat_result, key_file: Path | None) -> bool:
    if key_file is None:
        return False
    try:
        return os.path.samestat(status, os.stat(key_file))
    except OSError:
        return False


def restart_files(directory: Path, key_file: Path | None, *, pack_only: bool = False) -> list[Path]:
    """The files Start again may touch, in order (fixed names first, WAVs last), after a precheck of every one.

    Exact allowlisted names only (from a directory listing, never a glob). Each is `lstat`ed, never followed: a symlink
    (a dangling one too), a directory, a hard-linked file or the key file raises `NotOrdinary`, and so does an `audio`
    entry that is not a real directory. An unreadable folder raises `OSError`. With `pack_only` (the pack's delete-first
    rule) only the manifest and the timeline are listed and judged: `audio/` and the other files are not looked at.
    """
    project_names = os.listdir(directory)
    if pack_only:
        return _checked([directory / name for name in pack_output_names(project_names)], key_file)
    audio_names: list[str] = []
    if "audio" in project_names:
        if not stat.S_ISDIR(os.lstat(directory / "audio").st_mode):
            raise NotOrdinary("audio is not a real directory")
        audio_names = os.listdir(directory / "audio")
    return _checked([directory / name for name in restart_names(project_names, audio_names)], key_file)


def _checked(paths: list[Path], key_file: Path | None) -> list[Path]:
    for path in paths:
        status = os.lstat(path)
        if not stat.S_ISREG(status.st_mode) or status.st_nlink != 1 or _is_key(status, key_file):
            raise NotOrdinary(path.name)
    return paths
