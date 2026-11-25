from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .job_observer import JobObserver


@dataclass(frozen=True)
class JobSpec:
    """One job: sequential CLI runs and the hooks around them.

    `runs` are argument lists (the runner adds the interpreter prefix). `on_success()` runs only after every run
    exited 0 and returns a failure message or None. `on_finish(outcome, scenes_done)` runs once in every outcome
    (`done`, `failed` or `cancelled`) and returns `(failure_message, notice)`. `cleanup` paths are deleted last.
    """

    kind: str
    mode: str
    project: str
    runs: Sequence[Sequence[str]]
    total: int = 0
    scene: int | None = None
    cleanup: Sequence[Path] = ()
    on_success: Callable[[], str | None] | None = None
    on_finish: Callable[[str, int], tuple[str | None, str | None]] | None = None
    observer: JobObserver | None = None
