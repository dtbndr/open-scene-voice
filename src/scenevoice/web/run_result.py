from dataclasses import dataclass


@dataclass(frozen=True)
class RunResult:
    """How the sequence of runs ended: an outcome (`done`, `failed`, `cancelled`), a failure message, runs completed."""

    outcome: str
    failure: str | None
    completed: int
