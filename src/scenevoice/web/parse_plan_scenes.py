import json

from .planned_scene import PlannedScene


def parse_plan_scenes(stdout: str) -> tuple[PlannedScene, ...] | None:
    """The scenes of the plan JSON on stdout, or None when it is not the expected shape.

    Parses the whole text (never by line: titles may hold U+2028 or U+0085); walks only the flat scene list.
    """
    try:
        plan = json.loads(stdout)
    except (ValueError, RecursionError):
        return None
    items = plan.get("scenes") if isinstance(plan, dict) else None
    if not isinstance(items, list):
        return None
    scenes = []
    for item in items:
        if not isinstance(item, dict):
            return None
        ordinal, title, body = item.get("ordinal"), item.get("title"), item.get("body")
        if type(ordinal) is not int or not isinstance(title, str) or not isinstance(body, str):
            return None
        scenes.append(PlannedScene(ordinal, title, body))
    return tuple(scenes)
