"""Shape check for one beat of a scene."""

from typing import Any

from scenevoice.beats.beats_constants import MAX_NOTE_CHARS
from scenevoice.beats.check_keys import check_keys
from scenevoice.beats.is_plain_int import is_plain_int

_KEYS = ("first", "last", "note")


def _note_problem(note: Any) -> str | None:
    if not isinstance(note, str):
        return "must be a string"
    if not note.strip():
        return "must not be blank"
    if len(note.splitlines()) != 1 or note != note.splitlines()[0]:
        return "must be a single line"
    if len(note) > MAX_NOTE_CHARS:
        return f"must be at most {MAX_NOTE_CHARS} characters"
    try:
        note.encode("utf-8")
    except UnicodeEncodeError:
        return "must be valid UTF-8 text"
    return None


def check_beat_shape(
    where: str, beat: Any, expected_first: int, segment_count: int
) -> str | None:
    """Return a one-line problem for `beat`, or None. `where` prefixes messages."""
    if not isinstance(beat, dict):
        return f"{where} must be an object"
    problem = check_keys(where, beat, _KEYS)
    if problem:
        return problem
    first, last = beat["first"], beat["last"]
    if not is_plain_int(first):
        return f"{where}.first must be an integer"
    if not is_plain_int(last):
        return f"{where}.last must be an integer"
    if first != expected_first:
        return f"{where}.first must be {expected_first}, got {first}"
    if last < first:
        return f"{where}.first must not exceed last"
    if last > segment_count:
        return f"{where}.last must be at most segment_count {segment_count}, got {last}"
    note_problem = _note_problem(beat["note"])
    if note_problem:
        return f"{where}.note {note_problem}"
    return None
