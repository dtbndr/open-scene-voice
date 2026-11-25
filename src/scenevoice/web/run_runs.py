from typing import TYPE_CHECKING

from .drain_pipes import drain_pipes
from .job_spec import JobSpec
from .run_result import RunResult
from .stdout_capture import StdoutCapture

if TYPE_CHECKING:
    from .job_runner import JobRunner

SPAWN_FAILURE = "SceneVoice could not start the job."
RUN_FAILURE = "SceneVoice stopped with an error before the job was finished."
_PIPE_GRACE = 30.0


def run_runs(runner: "JobRunner", spec: JobSpec) -> RunResult:
    """Run the spec's argument lists one after another; stop at the first non-zero exit or at a cancel request."""
    observer = spec.observer
    completed = 0
    for argv in spec.runs:
        try:
            child = runner.begin_run(argv)
        except OSError:
            return RunResult("failed", SPAWN_FAILURE, completed)
        if child is None:
            return RunResult("cancelled", None, completed)
        drain = drain_pipes(child.proc.stdout, child.proc.stderr, observer.line if observer else _ignore)  # type: ignore[arg-type]
        code = child.wait()
        try:
            captured = drain.join(_PIPE_GRACE)
        except TimeoutError:
            captured = StdoutCapture(b"", 0)
        runner.end_run(captured)
        if observer is not None:
            observer.flush()
        if code != 0:
            if runner.cancel_requested():
                return RunResult("cancelled", None, completed)
            return RunResult("failed", RUN_FAILURE, completed)
        completed += 1
        runner.note_run_completed(completed)
        if completed < len(spec.runs) and runner.cancel_requested():
            return RunResult("cancelled", None, completed)
    return RunResult("done", None, completed)


def _ignore(line: str) -> None:
    return None
