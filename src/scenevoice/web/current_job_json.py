from collections.abc import Mapping, Sequence

from .failure_from_events import failure_from_events
from .job_state import FINAL_STATES, IDLE, STARTING, JobStatus


class _Derive:
    """The default `failure`: take it from the events."""


DERIVE = _Derive()


def current_job_json(
    status: JobStatus, events: Sequence[Mapping[str, object]], failure: Mapping[str, object] | None | _Derive = DERIVE
) -> dict[str, object]:
    """The `GET /api/jobs/current` body: `state`, and `job` (null when idle).

    `started` is false only while the job is still `starting`; `finished` is true in the three final states and
    `completed` only in `done`. The failure comes from the job's events (see `failure_from_events`) unless the caller
    passes it (a retained run's own, or a live run's None). `run` is the run id.
    """
    if status.state == IDLE:
        return {"state": IDLE, "job": None}
    job: dict[str, object] = {
        "kind": status.kind,
        "mode": status.mode,
        "project": status.project,
        "scene": status.scene,
        "started": status.state != STARTING,
        "finished": status.state in FINAL_STATES,
        "completed": status.state == "done",
        "total": status.total,
        "scenes_done": status.scenes_done,
        "failure": failure_from_events(events, outcome=status.state, message=status.failure)
        if isinstance(failure, _Derive)
        else failure,
        "notice": status.notice,
        "run": status.run,
    }
    return {"state": status.state, "job": job}
