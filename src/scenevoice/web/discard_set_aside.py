from .file_ops import REAL_OPS, FileOps
from .set_aside import SetAside


def discard_set_aside(aside: SetAside, ops: FileOps = REAL_OPS) -> None:
    """Remove this attempt's backups (the new generation is committed); a failure leaves that one in place, never raises."""
    for _, backup in aside.moves:
        try:
            ops.unlink(backup)
        except OSError:
            continue
