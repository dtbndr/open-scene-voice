from dataclasses import replace
from typing import TYPE_CHECKING

from .failure_from_events import failure_from_events
from .job_spec import JobSpec
from .job_state import JobStatus
from .run_hooks import FAILURE_KIND, HOOK_FAILURE, run_hooks
from .run_result import RunResult
from .run_runs import run_runs
from .slot_handle import SlotHandle

if TYPE_CHECKING:
    from .job_runner import JobRunner


def run_job(runner: "JobRunner", handle: SlotHandle, spec: JobSpec) -> None:
    """The job thread: runs, then hooks and cleanup, then publishes the final status and frees the slot.

    Whatever goes wrong, the slot is freed last: a bug here must not leave the server unable to start another job.
    """
    try:
        result = run_runs(runner, spec)
    except Exception:
        result = RunResult("failed", HOOK_FAILURE, 0)
    runner.enter_hooks()
    try:
        final = run_hooks(runner, spec, result)
    except Exception:
        final = JobStatus(
            state="failed", kind=spec.kind, project=spec.project, mode=spec.mode, scene=spec.scene,
            total=spec.total, failure_kind=FAILURE_KIND, failure=HOOK_FAILURE,
        )
    final = replace(final, run=handle.run)  # the one stamp: the hub's `end` event and the retained status share it
    runner.join_stoppers()
    runner.finish(handle, final, _own_failure(spec, final))
    if spec.observer is not None:
        try:
            spec.observer.end(final)
        except Exception:
            return


def _own_failure(spec: JobSpec, final: JobStatus) -> dict[str, object] | None:
    """This job's failure body, from its own observer's last `fail` event (never from the shared hub)."""
    try:
        last = getattr(spec.observer, "last_fail", None)
        return failure_from_events([last] if last else [], outcome=final.state, message=final.failure)
    except Exception:
        return None
