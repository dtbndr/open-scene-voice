import time
from collections.abc import Iterator

from .format_sse import format_sse
from .job_events import JobEvents
from .job_runner import JobRunner
from .job_state import LIVE_STATES
from .keepalive_comment import KEEPALIVE_COMMENT
from .snapshot_event import snapshot_event


def follow_job(
    runner: JobRunner,
    hub: JobEvents,
    job: int | None,
    after: int,
    keepalive: float = 15.0,
    poll: float = 0.5,
) -> Iterator[bytes]:
    """The body of an events stream: the state snapshot, then the job's events after `after`, then live ones.

    `job` is the job number to follow (or None to wait for the next one to begin); the stream ends after the job's
    `end` event, when the server shuts down, or, with no job, when the slot is no longer held. A `: keepalive`
    comment goes out every `keepalive` seconds of quiet. Nothing here holds a lock while a chunk is being yielded.
    """
    return _stream(runner, hub, job, after, keepalive, poll, hub.latest().number)


def _stream(
    runner: JobRunner, hub: JobEvents, job: int | None, after: int, keepalive: float, poll: float, baseline: int
) -> Iterator[bytes]:
    events = hub.latest_events() if job is not None else []
    yield format_sse(0, snapshot_event("state", 1, runner.current(), events))
    sent = time.monotonic()
    wait = min(keepalive, poll)
    while True:
        read = hub.read(job, after, wait, baseline)
        if job is None and read.job:
            job = read.job
        if read.events:
            for event in read.events:
                yield format_sse(job or 0, event)
            after = int(str(read.events[-1]["seq"]))
            sent = time.monotonic()
            continue  # the next read finds the job ended with nothing left, and closes
        if read.closed or (job is not None and read.ended):
            return
        if job is None:
            status = runner.current()
            if status.state not in LIVE_STATES:
                yield format_sse(0, snapshot_event("end", 2, status, []))
                return
        if time.monotonic() - sent >= keepalive:
            yield KEEPALIVE_COMMENT
            sent = time.monotonic()
