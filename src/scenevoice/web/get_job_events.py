from .follow_job import follow_job
from .job_events import JobEvents
from .job_runner import JobRunner
from .job_state import FINAL_STATES, IDLE
from .parse_last_event_id import parse_last_event_id
from .request import Request
from .route_table import Handler
from .stream_response import StreamResponse

_HEADERS = (("Content-Type", "text/event-stream; charset=utf-8"),)


def get_job_events(runner: JobRunner, hub: JobEvents, keepalive: float = 15.0, poll: float = 0.5) -> Handler:
    """GET /api/jobs/current/events: server-sent events for the newest job; reads only, writes nothing itself.

    A `Last-Event-ID` is only read: its job part must be the current job's, else it counts as absent (replay from
    the start). With no running or reserved job a reconnect gets 204, so `EventSource` stops asking.
    """

    def handle(request: Request) -> StreamResponse:
        status = runner.current()
        latest = hub.latest()
        resume = parse_last_event_id(request.header("last-event-id"))
        held = status.state != IDLE and status.state not in FINAL_STATES
        follows = latest.number > 0 and (latest.live or status.state in FINAL_STATES)
        if resume is not None and not held:
            if not follows or (resume[0] == latest.number and latest.end_seq and resume[1] >= latest.end_seq):
                return StreamResponse(204, (), iter(()))
        job = latest.number if follows else None
        after = resume[1] if resume is not None and resume[0] == job else 0
        return StreamResponse(200, _HEADERS, follow_job(runner, hub, job, after, keepalive, poll))

    return handle
