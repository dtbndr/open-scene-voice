from collections.abc import Sequence

from scenevoice.synth.limits import MAX_TEXT_BYTES
from scenevoice.synth.plan_scene import PlanScene
from scenevoice.validation import Violation

_RULE = "synth-limit"


def check_body_bytes(scenes: Sequence[PlanScene], model: str) -> Violation | None:
    """Every scene body alone against the UTF-8 byte limit; `model` is ignored.

    Assumes encodable text (the plan check runs first).
    """
    offenders = []
    for scene in scenes:
        size = len(scene.body.encode("utf-8"))
        if size > MAX_TEXT_BYTES:
            offenders.append(f"scene {scene.ordinal}: {size} bytes")
    if offenders:
        return Violation(
            _RULE,
            f"body over {MAX_TEXT_BYTES} UTF-8 bytes: " + "; ".join(offenders),
        )
    return None
