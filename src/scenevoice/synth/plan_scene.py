from dataclasses import dataclass


@dataclass(frozen=True)
class PlanScene:
    ordinal: int
    title: str
    body: str
