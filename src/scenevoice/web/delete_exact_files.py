from pathlib import Path

from .file_ops import REAL_OPS, FileOps
from .restart_files import restart_files


def delete_exact_files(directory: Path, key_file: Path | None, ops: FileOps = REAL_OPS, *, pack_only: bool = False) -> None:
    """Delete every allowlisted Start again file now present, the WAVs last; nothing at all if any one is not ordinary.

    `NotOrdinary` is raised by the precheck before the first deletion; an `OSError` stops the rest and says nothing
    was completed (the caller never claims a clean state). With `pack_only` only the manifest and the timeline go.
    """
    for path in restart_files(directory, key_file, pack_only=pack_only):
        ops.unlink(path)
