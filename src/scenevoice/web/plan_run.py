from dataclasses import dataclass

from .planned_scene import PlannedScene


@dataclass(frozen=True)
class PlanRun:
    """A passed plan: the exact stdout bytes the child printed, the scenes in them and the script revision."""

    stdout: bytes
    scenes: tuple[PlannedScene, ...]
    revision: str
