"""Helpers for the job-runner tests: polling waits, a recording observer and short-constant runners."""

import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scenevoice.web import JobRunner, JobSpec
from scenevoice.web.job_state import FINAL_STATES, JobStatus

TIMEOUT = 15.0
KILL_DELAY = 0.3


def wait_until(predicate: Callable[[], Any], timeout: float = TIMEOUT) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition not reached in time")
        time.sleep(0.005)


class RecordingObserver:
    """Collects raw lines, flushes and the end status; `log` (shared with hooks) records their order."""

    def __init__(self, runner: JobRunner | None = None, log: list[str] | None = None) -> None:
        self.runner = runner
        self.lines: list[str] = []
        self.flushes = 0
        self.ends: list[JobStatus] = []
        self.log = log if log is not None else []

    def line(self, text: str) -> None:
        self.lines.append(text)
        if self.runner is not None and text == "scene done":
            self.runner.note_scene_done()

    def flush(self) -> None:
        self.flushes += 1
        self.log.append("flush")

    def end(self, status: JobStatus) -> None:
        self.ends.append(status)
        self.log.append("end")


def make_runner(stub: Any, tmp_path: Path, **options: Any) -> JobRunner:
    cwd = tmp_path / "launch"
    cwd.mkdir(exist_ok=True)
    arguments: dict[str, Any] = {
        "cwd": cwd, "env": dict(os.environ), "prefix": stub.prefix if stub is not None else None, "kill_delay": KILL_DELAY, "shutdown_bound": 10.0,
    }
    return JobRunner(**{**arguments, **options})


def start_job(runner: JobRunner, runs: Any = (("synth", "1"),), **fields: Any) -> JobSpec:
    spec = JobSpec(**{"kind": "synth", "mode": "all", "project": "p", "runs": runs, "total": len(runs), **fields})
    handle = runner.reserve(spec.kind, spec.project)
    assert handle is not None
    runner.start(handle, spec)
    return spec


def wait_final(runner: JobRunner) -> JobStatus:
    wait_until(lambda: runner.current().state in FINAL_STATES)
    return runner.current()


def run_to_end(runner: JobRunner, runs: Any = (("synth", "1"),), **fields: Any) -> JobStatus:
    start_job(runner, runs, **fields)
    return wait_final(runner)


def wait_started(stub: Any, count: int = 1) -> None:
    wait_until(lambda: len([event for event in stub.events() if event["event"] == "start"]) >= count)


def pid_gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


class Gate:
    """A hook that blocks until released; `entered` is set when the hook starts."""

    def __init__(self, result: Any) -> None:
        self.entered = threading.Event()
        self.open = threading.Event()
        self.result = result
        self.calls: list[tuple[Any, ...]] = []

    def __call__(self, *args: Any) -> Any:
        self.calls.append(args)
        self.entered.set()
        assert self.open.wait(TIMEOUT)
        return self.result
