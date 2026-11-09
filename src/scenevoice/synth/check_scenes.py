from scenevoice.synth.is_text_blank import is_text_blank
from scenevoice.synth.plan_scene import PlanScene
from scenevoice.validation import Violation

_RULE = "plan-input"
_KEYS = {"ordinal", "title", "body"}


def _bad(message: str) -> Violation:
    return Violation(_RULE, message)


def check_scenes(document: object) -> list[PlanScene] | Violation:
    """Shape and field checks on a parsed plan document. Never raises."""
    if not isinstance(document, dict) or set(document) != {"scenes"}:
        return _bad("plan must be an object whose only key is 'scenes'")
    items = document["scenes"]
    if not isinstance(items, list) or not items:
        return _bad("'scenes' must be a non-empty array")
    scenes: list[PlanScene] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict) or set(item) != _KEYS:
            return _bad(
                f"scene {index} must be an object with exactly ordinal, title and body"
            )
        ordinal, title, body = item["ordinal"], item["title"], item["body"]
        if type(ordinal) is not int:
            return _bad(f"scene {index}: ordinal must be a JSON integer")
        if ordinal != index:
            return _bad(f"scene {index}: ordinal must be {index}, got {ordinal}")
        if not isinstance(title, str):
            return _bad(f"scene {index}: title must be a string")
        if not isinstance(body, str):
            return _bad(f"scene {index}: body must be a string")
        if is_text_blank(body):
            return _bad(f"scene {index}: body is blank")
        try:
            body.encode("utf-8")
        except UnicodeEncodeError:
            return _bad(f"scene {index}: body cannot be encoded as UTF-8")
        scenes.append(PlanScene(ordinal, title, body))
    return scenes
