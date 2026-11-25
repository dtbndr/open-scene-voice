"""Set check of a parsed beats reply against the script's segments (WS35 decision 5)."""

from typing import Any

from scenevoice.beats.check_beat_shape import check_beat_shape
from scenevoice.beats.is_plain_int import is_plain_int


def check_beats_coverage(segment_counts: list[int], parsed: list[dict[str, Any]]) -> list[str]:
    """Return one-line problems (empty when the reply is good).

    Every segment of every scene must sit in exactly one beat, in order, with
    no gaps; scene numbers must be 1..N in order. Beat and note rules come
    from `check_beat_shape`, the same check the sidecar shape check uses.
    """
    problems: list[str] = []
    for position, count in enumerate(segment_counts, start=1):
        if position > len(parsed):
            problems.append(f"scene {position} is missing from the reply")
            continue
        scene = parsed[position - 1]
        number = scene["scene"]
        if not is_plain_int(number) or number != position:
            problems.append(f"scene {position} is numbered {number!r} in the reply")
            continue
        problem = _beats_problem(position, count, scene["beats"])
        if problem:
            problems.append(problem)
    for position in range(len(segment_counts) + 1, len(parsed) + 1):
        problems.append(f"scene {position} is not in the script")
    return problems


def _beats_problem(position: int, count: int, beats: list[Any]) -> str | None:
    if count == 0:
        if beats:
            return f"scene {position} has no sentences but the reply gives beats"
        return None
    if not beats:
        return f"scene {position} has {count} sentences but no beats"
    expected_first = 1
    for i, beat in enumerate(beats, start=1):
        problem = check_beat_shape(f"scene {position}.beats[{i}]", beat, expected_first, count)
        if problem:
            return problem
        expected_first = beat["last"] + 1
    if expected_first - 1 != count:
        return f"scene {position}: beats end at {expected_first - 1} but the scene has {count} sentences"
    return None
