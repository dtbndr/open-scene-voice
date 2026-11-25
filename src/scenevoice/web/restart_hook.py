from collections.abc import Callable
from pathlib import Path

from .delete_exact_files import delete_exact_files
from .discard_set_aside import discard_set_aside
from .file_ops import REAL_OPS, FileOps
from .not_ordinary import NotOrdinary
from .restart_messages import ROLLBACK_FAILED, SPARE_COPIES
from .restore_set_aside import restore_set_aside
from .set_aside import SetAside


def restart_hook(
    aside: SetAside, directory: Path, key_file: Path | None, ops: FileOps = REAL_OPS
) -> Callable[[str, int], tuple[str | None, str | None]]:
    """The job's `on_finish` for Start again: commit (discard the backups) or roll the whole old generation back (J4).

    The commit point is the first `done` scene (or a `done` job): the CLI installs a scene's WAV before it writes the
    record and emits `scene done`, so any earlier end leaves a mixed set that must not stand. A rollback first removes
    every allowlisted output now present (all old ones were set aside, so they are this attempt's), then restores the
    backups; if it cannot finish, every backup is kept and the job fails with the could-not-be-put-back message.
    Only this attempt's recorded names are ever restored or discarded.
    """

    def on_finish(outcome: str, scenes_done: int) -> tuple[str | None, str | None]:
        if outcome == "done" or scenes_done > 0:
            discard_set_aside(aside, ops)
            return None, None
        try:
            delete_exact_files(directory, key_file, ops)
        except (NotOrdinary, OSError):
            return ROLLBACK_FAILED, None
        result = restore_set_aside(aside, ops)
        if result == "failed":
            return ROLLBACK_FAILED, None
        return None, SPARE_COPIES if result == "spares" else None

    return on_finish
