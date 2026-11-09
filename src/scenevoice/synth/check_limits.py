from scenevoice.synth.check_body_bytes import check_body_bytes
from scenevoice.synth.limits import MAX_SCENES
from scenevoice.synth.plan_scene import PlanScene
from scenevoice.synth.provider_registry import BodyCheck
from scenevoice.validation import Violation

_RULE = "synth-limit"


def check_limits(
    scenes: list[PlanScene], *, body_check: BodyCheck | None = None
) -> Violation | None:
    """Scene count first, then the provider's body check (default: the Vertex byte check).

    Assumes encodable text (the plan check runs first).
    """
    if len(scenes) > MAX_SCENES:
        return Violation(
            _RULE, f"{len(scenes)} scenes exceeds the maximum of {MAX_SCENES}"
        )
    if body_check is None:
        return check_body_bytes(scenes, "")
    return body_check(scenes)
