import json


def plan_scene_count(stdout: str) -> int | None:
    """Number of scenes in the plan JSON on stdout, or None when it is not the expected shape.

    Parses the whole text (never by line: titles may hold U+2028 or U+0085).
    """
    try:
        plan = json.loads(stdout)
    except ValueError:
        return None
    scenes = plan.get("scenes") if isinstance(plan, dict) else None
    return len(scenes) if isinstance(scenes, list) else None
