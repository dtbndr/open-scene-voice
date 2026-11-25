from collections import deque
from typing import NamedTuple

from .job_state import JobStatus

RETAINED = 8


class RunLookup(NamedTuple):
    """What a lookup by run id finds: that run's status and, for a failed final, its own failure body (else None)."""

    status: JobStatus
    failure: dict[str, object] | None


class RetainedFinals:
    """The last few final statuses, keyed by run id, so a page whose run was replaced can still learn how it ended.

    Not thread-safe by itself: the runner calls it under its own lock.
    """

    def __init__(self, limit: int = RETAINED) -> None:
        self._items: deque[tuple[str, RunLookup]] = deque(maxlen=limit)

    def put(self, run: str, status: JobStatus, failure: dict[str, object] | None) -> None:
        self._items.append((run, RunLookup(status, failure)))

    def get(self, run: str) -> RunLookup | None:
        return next((found for key, found in self._items if key == run), None)
