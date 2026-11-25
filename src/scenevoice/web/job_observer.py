from typing import Protocol

from .job_state import JobStatus


class JobObserver(Protocol):
    """What the runner hands a job's output to; slice D supplies the real one (the runner parses nothing)."""

    def line(self, text: str) -> None:
        """One raw stderr line, in order, from the drain thread."""

    def flush(self) -> None:
        """Both pipes are at EOF; called once per run, before any hook."""

    def end(self, status: JobStatus) -> None:
        """The final status, after the hooks have finished and the slot is free; called once per job."""
