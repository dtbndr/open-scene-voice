from dataclasses import dataclass


@dataclass(frozen=True)
class PlanProblem:
    """One script problem for the UI: the 1-based line (None when the CLI gives none) and a plain message."""

    line: int | None
    message: str
