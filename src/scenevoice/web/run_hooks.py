from typing import TYPE_CHECKING

from .cleanup_paths import cleanup_paths
from .job_spec import JobSpec
from .job_state import JobStatus
from .run_result import RunResult

if TYPE_CHECKING:
    from .job_runner import JobRunner

HOOK_FAILURE = "SceneVoice could not finish the job."
FAILURE_KIND = "other"


def run_hooks(runner: "JobRunner", spec: JobSpec, result: RunResult) -> JobStatus:
    """`on_success` (only after a clean finish), `on_finish` (always), then the cleanup; returns the final status.

    A returned failure message ends the job `failed`. A notice is carried along and never changes the outcome.
    """
    outcome, failure, notice = result.outcome, result.failure, None
    if outcome == "done" and spec.on_success is not None:
        try:
            message = spec.on_success()
        except Exception:
            message = HOOK_FAILURE
        if message:
            outcome, failure = "failed", message
    if spec.on_finish is not None:
        try:
            message, notice = spec.on_finish(outcome, runner.scenes_done())
        except Exception:
            message, notice = HOOK_FAILURE, None
        if message:
            outcome, failure = "failed", message
    cleanup_paths(spec.cleanup)
    return JobStatus(
        state=outcome,
        kind=spec.kind,
        project=spec.project,
        mode=spec.mode,
        scene=spec.scene,
        scenes_done=runner.final_scenes_done(len(spec.runs), result.completed),
        total=spec.total,
        failure_kind=FAILURE_KIND if outcome == "failed" else None,
        failure=failure if outcome == "failed" else None,
        notice=notice,
    )
