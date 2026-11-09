from dataclasses import dataclass

from scenevoice.synth.plan_scene import PlanScene
from scenevoice.synth.record_entry import RecordEntry


@dataclass(frozen=True)
class PreflightResult:
    scenes: list[PlanScene]
    env: dict[str, str]
    total: int = 0  # the plan's scene count, also in scene mode where `scenes` has one entry
    entries: tuple[RecordEntry, ...] = ()  # scene mode: the parsed synth_record.json entries, else empty
    plan: tuple[PlanScene, ...] = ()  # every plan scene in plan order, in full and scene mode
