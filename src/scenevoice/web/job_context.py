import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .cli_result import CliResult
from .file_ops import REAL_OPS, FileOps
from .job_events import JobEvents
from .job_runner import JobRunner


@dataclass(frozen=True)
class JobContext:
    """What one server's start route needs: the workspace, the plan runner, the two locks, the runner, the event hub and the filesystem moves of Start again."""

    root_getter: Callable[[], Path]
    run: Callable[..., CliResult]
    key_file: Path | None
    launch_dir: Path
    check_lock: threading.Lock
    script_lock: threading.Lock
    runner: JobRunner
    events: JobEvents
    ops: FileOps = REAL_OPS
