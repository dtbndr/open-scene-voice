"""Shape check for one scene of the sidecar."""

from typing import Any

from scenevoice.beats.check_beat_shape import check_beat_shape
from scenevoice.beats.check_keys import check_keys
from scenevoice.beats.is_plain_int import is_plain_int

_KEYS = ("ordinal", "title", "segment_count", "beats")


def check_scene_shape(position: int, scene: Any) -> str | None:
    """Return a one-line problem for the scene at 1-based `position`, or None."""
    where = f"scenes[{position}]"
    if not isinstance(scene, dict):
        return f"{where} must be an object"
    problem = check_keys(where, scene, _KEYS)
    if problem:
        return problem
    ordinal = scene["ordinal"]
    if not is_plain_int(ordinal) or ordinal != position:
        return f"{where}.ordinal must be the integer {position}"
    title = scene["title"]
    if not isinstance(title, str):
        return f"{where}.title must be a string"
    try:
        title.encode("utf-8")
    except UnicodeEncodeError:
        return f"{where}.title must be valid UTF-8 text"
    count = scene["segment_count"]
    if not is_plain_int(count) or count < 0:
        return f"{where}.segment_count must be a non-negative integer"
    beats = scene["beats"]
    if not isinstance(beats, list):
        return f"{where}.beats must be a list"
    if count == 0:
        return None if not beats else f"{where}.beats must be empty when segment_count is 0"
    if not beats:
        return f"{where}.beats must not be empty when segment_count is {count}"
    expected_first = 1
    for i, beat in enumerate(beats, start=1):
        problem = check_beat_shape(f"{where}.beats[{i}]", beat, expected_first, count)
        if problem:
            return problem
        expected_first = beat["last"] + 1
    if expected_first - 1 != count:
        return f"{where}.beats[{len(beats)}].last must be segment_count {count}"
    return None
