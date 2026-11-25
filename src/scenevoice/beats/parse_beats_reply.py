"""Parse a cleaned beats reply into per-scene beats (WS35 decision 6)."""

import json
from typing import Any

from scenevoice.beats.check_keys import check_keys


def parse_beats_reply(text: str) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Return (scenes, None) for the model-facing shape, else (None, one-line problem).

    Only the structure is checked here: an object with exactly `scenes`, each
    scene an object with exactly `scene` and `beats`, `beats` a list. Numbers,
    ranges and notes are judged by `check_beats_coverage`.
    """
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as error:
        return None, f"the reply is not valid JSON ({error})"
    if not isinstance(data, dict):
        return None, "the reply's top level must be an object"
    problem = check_keys("reply", data, ("scenes",))
    if problem:
        return None, problem
    scenes = data["scenes"]
    if not isinstance(scenes, list):
        return None, "reply.scenes must be a list"
    for position, scene in enumerate(scenes, start=1):
        where = f"scenes[{position}]"
        if not isinstance(scene, dict):
            return None, f"{where} must be an object"
        problem = check_keys(where, scene, ("scene", "beats"))
        if problem:
            return None, problem
        if not isinstance(scene["beats"], list):
            return None, f"{where}.beats must be a list"
    return scenes, None
