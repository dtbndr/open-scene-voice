from collections.abc import Mapping, Sequence

from .current_job_json import current_job_json
from .job_state import JobStatus


def snapshot_event(
    kind: str, seq: int, status: JobStatus, events: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    """A `state` or `end` event: the current-job JSON plus its `seq` and `type`."""
    return {"seq": seq, "type": kind, **current_job_json(status, events)}
