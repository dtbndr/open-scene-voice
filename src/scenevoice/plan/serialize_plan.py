import json

from scenevoice.validation.scene import Scene


def serialize_plan(scenes: list[Scene]) -> str:
    # Explicit dicts so Scene.line can never leak into the plan.
    plan = {
        "scenes": [
            {"ordinal": s.ordinal, "title": s.title, "body": s.body} for s in scenes
        ]
    }
    return json.dumps(plan, ensure_ascii=False) + "\n"
