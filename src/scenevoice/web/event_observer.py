import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from .job_state import JobStatus
from .parse_event_line import parse_event_line
from .progress_vocabulary import MESSAGE_LIMIT

if TYPE_CHECKING:
    from .job_events import JobEvents


class EventObserver:
    """One job's `JobObserver`: parses each stderr line into a safe event, scrubs its message, buffers it.

    Lines that are not known events are dropped here and never forwarded. Every call is guarded: a failing
    scrub drops the event (never forwards it unscrubbed) and a failing counter does not lose the event.
    """

    def __init__(self, hub: "JobEvents", scrub: Callable[[str], str], on_scene_done: Callable[[], None]) -> None:
        self._hub = hub
        self._scrub = scrub
        self._on_scene_done = on_scene_done
        self._ended = False
        self.last_fail: dict[str, object] | None = None  # this job's last scrubbed `fail` event, read at finish
        self._lock = threading.Lock()  # makes "not ended, so open" and "end" one step each (lock order: this, then the hub's)

    def line(self, text: str) -> None:
        event = parse_event_line(text)
        if event is None:
            return
        if event["type"] == "scene" and event.get("state") == "done":
            try:
                self._on_scene_done()
            except Exception:
                pass
        try:
            event["message"] = self._scrub(str(event["message"]))[:MESSAGE_LIMIT]  # scrub the whole text, then cut
        except Exception:
            return
        if event["type"] == "fail":
            self.last_fail = event
        self._hub.add(event)

    def flush(self) -> None:
        with self._lock:
            if not self._ended:  # a flush that comes after this job's end must not open an empty job
                self._hub.begin()

    def end(self, status: JobStatus) -> None:
        with self._lock:
            self._ended = True
            self._hub.finish(status)
