from collections.abc import Sequence

from scenevoice.synth.plan_scene import PlanScene


def neighbour_texts(plan: Sequence[PlanScene], ordinal: int) -> tuple[str | None, str | None]:
    """Return (previous_text, next_text): the whole bodies of scenes ordinal - 1 and ordinal + 1.

    A missing neighbour (first, last or only scene) is None. Relies on the plan check: ordinals
    are consecutive from 1 in array order.
    """
    previous = plan[ordinal - 2].body if ordinal >= 2 else None
    following = plan[ordinal].body if ordinal < len(plan) else None
    return previous, following
