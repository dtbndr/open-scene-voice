"""Shared doubles and parsers for the job events tests: a fake runner, status builders and an SSE reader."""

import json
from collections.abc import Iterable
from typing import Any

from scenevoice.web import JobEvents, JobStatus


class FakeRunner:
    """Just enough of JobRunner for the routes: a settable status, an active flag and a cancel counter."""

    def __init__(self, status: JobStatus | None = None, active: bool = False) -> None:
        self.status = status or JobStatus()
        self.active = active
        self.cancels = 0
        self.retained: dict[str, tuple[JobStatus, dict[str, object] | None]] = {}

    def current(self) -> JobStatus:
        return self.status

    def job_active(self) -> bool:
        return self.active

    def cancel(self) -> None:
        raise AssertionError("the cancel route must use cancel_run, never the unbound cancel()")

    def cancel_run(self, run: str) -> str:
        if not self.active:
            return "nothing"
        if run != self.status.run:
            return "stale"
        self.cancels += 1
        return "stopped"

    def lookup(self, run: str) -> tuple[JobStatus, dict[str, object] | None] | None:
        if self.status.run == run and self.status.state in ("starting", "running", "cancelling"):
            return self.status, None
        return self.retained.get(run)


def status_of(state: str, **fields: Any) -> JobStatus:
    base: dict[str, Any] = {"kind": "synth", "mode": "all", "project": "my-video", "total": 3}
    return JobStatus(state=state, **{**base, **fields})


def scene_event(scene: int, state: str = "done") -> dict[str, Any]:
    return {"type": "scene", "command": "synth", "message": f"scene {scene}", "state": state, "scene": scene, "total": 3}


def finished_hub(count: int = 3, state: str = "done", limit: int = 5000, **fields: Any) -> JobEvents:
    """A hub holding one finished job of `count` scene events plus its `end`."""
    hub = JobEvents(limit)
    for number in range(1, count + 1):
        hub.add(scene_event(number))
    hub.finish(status_of(state, scenes_done=count, **fields))
    return hub


def parse_sse(data: bytes) -> list[tuple[str, dict[str, Any]]]:
    """(id, event object) for each event; comment lines are skipped."""
    events = []
    for block in data.decode("utf-8").split("\n\n"):
        lines = [line for line in block.split("\n") if line and not line.startswith(":")]
        if not lines:
            continue
        assert [line.split(": ", 1)[0] for line in lines] == ["id", "data"]
        events.append((lines[0][4:], json.loads(lines[1][6:])))
    return events


def sse_of(chunks: Iterable[bytes]) -> list[tuple[str, dict[str, Any]]]:
    return parse_sse(b"".join(chunks))
