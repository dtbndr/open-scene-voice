from dataclasses import dataclass

from .plan_problem import PlanProblem


@dataclass(frozen=True)
class ScriptBytes:
    """The saved script as read: its exact bytes, or a problem when it cannot be used; both None when absent."""

    data: bytes | None = None
    problem: PlanProblem | None = None
