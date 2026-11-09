from pathlib import Path

from scenevoice.synth.limits import MAX_SCENES
from scenevoice.synth.load_plan import load_plan
from scenevoice.synth.plan_scene import PlanScene
from scenevoice.synth.read_plan_input import read_plan_input
from scenevoice.validation import Violation


def _text(violation: Violation) -> str:
    suffix = f" (line {violation.line})" if violation.line is not None else ""
    return violation.message + suffix


def check_pack_plan(plan_path: str | Path | None, stdin) -> list[PlanScene] | str:
    """Read and check the plan for pack: the scenes, or a one-line message (no prefix).

    Order: read, load, scene count, title encodability. The synth body byte
    limit is deliberately not applied. Never looks at a terminal.
    """
    data = read_plan_input(plan_path, stdin)
    if isinstance(data, Violation):
        return _text(data)
    scenes = load_plan(data)
    if isinstance(scenes, Violation):
        return _text(scenes)
    if len(scenes) > MAX_SCENES:
        return f"{len(scenes)} scenes exceeds the maximum of {MAX_SCENES}"
    for scene in scenes:
        try:
            scene.title.encode("utf-8")
        except UnicodeEncodeError:
            return f"scene {scene.ordinal}: title cannot be encoded as UTF-8"
    return scenes
