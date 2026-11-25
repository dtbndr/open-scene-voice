import threading
from collections.abc import Callable
from pathlib import Path

from .real_root import real_root
from .workspace_error import WorkspaceKeyFileError


def make_root_getter(workspace: Path, key_file: Path | None) -> Callable[[], Path]:
    """The per-server memoised root: `real_root` runs on first use only, and a refusal is remembered too.

    Raises `WorkspaceKeyFileError` on every call when the resolved root holds the key file.
    """
    lock = threading.Lock()
    outcome: list[Path | str] = []

    def get() -> Path:
        with lock:
            if not outcome:
                try:
                    outcome.append(real_root(workspace, key_file))
                except WorkspaceKeyFileError as error:
                    outcome.append(str(error))
            result = outcome[0]
        if isinstance(result, str):
            raise WorkspaceKeyFileError(result)
        return result

    return get
