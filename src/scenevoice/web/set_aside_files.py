import secrets
from pathlib import Path

from .file_ops import REAL_OPS, FileOps
from .restart_files import restart_files
from .set_aside import SetAside, SetAsideFailed


def set_aside_files(directory: Path, key_file: Path | None, ops: FileOps = REAL_OPS, token: str | None = None) -> SetAside:
    """Rename every allowlisted Start again file in place to `.write-restart-<token>-<name>.tmp` (J4, the default build).

    The precheck of `restart_files` covers every file first (`NotOrdinary` and no rename at all). The token is random
    per attempt; the returned record names exactly the moves made, and nothing else is ever restored or discarded.
    A rename that fails raises `SetAsideFailed` carrying the moves that did happen.
    """
    paths = restart_files(directory, key_file)
    token = token or secrets.token_hex(8)
    done: list[tuple[Path, Path]] = []
    for path in paths:
        backup = path.with_name(f".write-restart-{token}-{path.name}.tmp")
        try:
            ops.rename(path, backup)
        except OSError as error:
            raise SetAsideFailed(SetAside(tuple(done))) from error
        done.append((path, backup))
    return SetAside(tuple(done))
