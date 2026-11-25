from dataclasses import dataclass


@dataclass(frozen=True)
class PlannedScene:
    """One scene of the plan JSON: the ordinal, the title and the body text (the voiced text)."""

    ordinal: int
    title: str
    body: str
