from collections.abc import Sequence

from scenevoice.synth.limits import ELEVENLABS_CHAR_LIMITS
from scenevoice.synth.plan_scene import PlanScene
from scenevoice.validation import Violation

_RULE = "synth-limit"


def check_body_chars(scenes: Sequence[PlanScene], model: str) -> Violation | None:
    """Every scene body alone against the model's code-point limit.

    Assumes encodable text (the plan check runs first); ignores the scene count.
    """
    limit = ELEVENLABS_CHAR_LIMITS[model]
    offenders = []
    for scene in scenes:
        size = len(scene.body)
        if size > limit:
            offenders.append(f"scene {scene.ordinal}: {size} characters")
    if offenders:
        return Violation(_RULE, f"body over {limit} characters: " + "; ".join(offenders))
    return None
