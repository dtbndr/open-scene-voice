from pathlib import Path

from .file_ops import REAL_OPS, FileOps
from .set_aside import SetAside


def _unlink_quietly(paths: list[Path], ops: FileOps) -> None:
    for path in paths:
        try:
            ops.unlink(path)
        except OSError:
            continue


def restore_set_aside(aside: SetAside, ops: FileOps = REAL_OPS) -> str:
    """Put this attempt's backups back by a three-phase COPY restore: "restored", "spares" or "failed".

    The original names must be absent (the caller removed anything a run created). Phase 1 copies each backup to a
    private `.write-restore-` temp; phase 2 `os.replace`s each temp into its original name (one link, atomic); only
    when every replace worked does phase 3 unlink the backups. A failure in phase 1 or 2 unlinks the temps best effort
    and keeps ALL backups ("failed"). A phase-3 unlink that fails leaves a stray backup ("spares": the audio is back).
    """
    temps: list[tuple[Path, Path]] = []
    try:
        for original, backup in aside.moves:
            temp = backup.with_name(backup.name.replace(".write-restart-", ".write-restore-", 1))
            temps.append((temp, original))  # listed first: a copy that dies half way leaves a temp to remove too
            ops.copy(backup, temp)
    except OSError:
        _unlink_quietly([temp for temp, _ in temps], ops)
        return "failed"
    for index, (temp, original) in enumerate(temps):
        try:
            ops.replace(temp, original)
        except OSError:
            _unlink_quietly([left for left, _ in temps[index:]], ops)
            return "failed"
    spares = False
    for _, backup in aside.moves:
        try:
            ops.unlink(backup)
        except OSError:
            spares = True
    return "spares" if spares else "restored"
