import threading
from collections.abc import Callable

from .event_observer import EventObserver
from .job_latest import JobLatest
from .job_observer import JobObserver
from .job_read import JobRead
from .job_state import JobStatus
from .snapshot_event import snapshot_event


class JobEvents:
    """The in-memory events of the newest job: one buffer (the last `limit` events), numbered jobs, a wake-up.

    A job is numbered from its first output (or its end) on; `add` and `finish` are called from the job's
    threads and `read` from the subscribers, all under one lock that nobody holds while writing to a socket.
    A new job replaces the previous job's buffer, so a subscriber always names the job it follows.
    """

    def __init__(self, limit: int = 5000) -> None:
        self._limit = limit
        self._cond = threading.Condition()
        self._number = 0
        self._events: list[dict[str, object]] = []
        self._seq = 0
        self._end_seq = 0
        self._open = False
        self._closed = False

    def observer(self, *, scrub: Callable[[str], str], on_scene_done: Callable[[], None]) -> JobObserver:
        """The `JobObserver` for the next job: `scrub` cleans each message, `on_scene_done` counts a finished scene."""
        return EventObserver(self, scrub, on_scene_done)

    def begin(self) -> None:
        """Make sure there is an open job (a new number and an empty buffer if the last one ended)."""
        with self._cond:
            self._begin_locked()

    def add(self, event: dict[str, object]) -> None:
        with self._cond:
            self._append_locked(event)
            self._cond.notify_all()

    def finish(self, status: JobStatus) -> None:
        """Append the job's `end` event (the final state) and close the job."""
        with self._cond:
            self._begin_locked()
            end = snapshot_event("end", self._seq + 1, status, self._events)
            self._append_locked(end)
            self._end_seq = self._seq
            self._open = False
            self._cond.notify_all()

    def latest(self) -> JobLatest:
        with self._cond:
            return JobLatest(self._number, self._open, self._end_seq)

    def latest_events(self) -> list[dict[str, object]]:
        with self._cond:
            return list(self._events)

    def read(self, job: int | None, after: int, timeout: float, newer_than: int = 0) -> JobRead:
        """Events of `job` with a seq above `after`, waiting up to `timeout` once if there are none yet.

        `job=None` follows the open job, or a job numbered above `newer_than`; job 0 in the answer means none yet.
        """
        with self._cond:
            result = self._read_locked(job, after, newer_than)
            if not result.events and not result.ended and not self._closed and timeout > 0:
                self._cond.wait(timeout)
                result = self._read_locked(job, after, newer_than)
            return result

    def close(self) -> None:
        with self._cond:
            self._closed = True
            self._cond.notify_all()

    def _begin_locked(self) -> None:
        if not self._open:
            self._number += 1
            self._events = []
            self._seq = 0
            self._end_seq = 0
            self._open = True

    def _append_locked(self, event: dict[str, object]) -> None:
        self._begin_locked()
        self._seq += 1
        self._events.append({**event, "seq": self._seq})
        del self._events[: -self._limit]

    def _read_locked(self, job: int | None, after: int, newer_than: int) -> JobRead:
        target = job
        if target is None:
            target = self._number if self._open or self._number > newer_than else 0
        if target == 0 or target != self._number:
            return JobRead(target, (), target != 0, self._closed)
        events = tuple(event for event in self._events if int(str(event["seq"])) > after)
        return JobRead(target, events, not self._open, self._closed)
