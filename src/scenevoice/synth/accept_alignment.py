import math

from scenevoice.synth.alignment import Alignment


def _as_time(value: object) -> float | None:
    """Return a finite non-negative float for a real JSON number, otherwise None. Never raises."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)  # an int beyond float range raises OverflowError
    except OverflowError:
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def accept_alignment(value: object) -> Alignment | str:
    """Apply the contract's element rules to a provider alignment object.

    Returns an unclamped Alignment (tuples, times as floats) or a short reason. Never raises and
    ignores extra keys. It does not check start-before-end, monotonic times or text equality.
    """
    if not isinstance(value, dict):
        return "alignment is not an object"
    characters = value.get("characters")
    starts = value.get("character_start_times_seconds")
    ends = value.get("character_end_times_seconds")
    if not (isinstance(characters, list) and isinstance(starts, list) and isinstance(ends, list)):
        return "alignment arrays are missing or not arrays"
    if not len(characters) == len(starts) == len(ends):
        return "alignment arrays differ in length"
    if not characters:
        return "alignment is empty"
    if not all(isinstance(c, str) for c in characters):
        return "alignment characters must be strings"
    start_times = [_as_time(t) for t in starts]
    end_times = [_as_time(t) for t in ends]
    if any(t is None for t in start_times) or any(t is None for t in end_times):
        return "alignment times must be finite non-negative numbers"
    return Alignment(
        tuple(characters),
        tuple(t for t in start_times if t is not None),
        tuple(t for t in end_times if t is not None),
    )
