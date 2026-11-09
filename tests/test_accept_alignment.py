import json
from pathlib import Path

import pytest

from scenevoice.synth import Alignment, accept_alignment

FIXTURES = Path(__file__).parent / "fixtures" / "elevenlabs"
NOT_OBJECT = "alignment is not an object"
ARRAYS = "alignment arrays are missing or not arrays"
TIMES = "alignment times must be finite non-negative numbers"


def _good():
    return {
        "characters": ["I", "t"],
        "character_start_times_seconds": [0.0, 0.128],
        "character_end_times_seconds": [0.128, 0.186],
    }


def _with(**changes):
    value = _good()
    value.update(changes)
    return value


def test_flash_fixture_arrays_give_tuples():
    doc = json.loads((FIXTURES / "success_flash.json").read_bytes())
    assert accept_alignment(doc["alignment"]) == Alignment(("I", "t"), (0.0, 0.128), (0.128, 0.186))


def test_integer_time_becomes_float():
    result = accept_alignment(_with(character_start_times_seconds=[0, 1]))
    assert isinstance(result, Alignment)
    assert result.character_start_times_seconds == (0.0, 1.0)
    assert all(type(t) is float for t in result.character_start_times_seconds)


def test_extra_keys_are_ignored():
    assert isinstance(accept_alignment(_with(extra="x")), Alignment)


def test_start_after_end_and_non_monotonic_times_are_accepted():
    value = _with(character_start_times_seconds=[5.0, 1.0], character_end_times_seconds=[2.0, 0.5])
    assert isinstance(accept_alignment(value), Alignment)


def _missing(key):
    value = _good()
    del value[key]
    return value


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ([], NOT_OBJECT),
        (None, NOT_OBJECT),
        (_missing("character_end_times_seconds"), ARRAYS),
        (_missing("characters"), ARRAYS),
        (_with(characters="It"), ARRAYS),
        (_with(character_start_times_seconds=None), ARRAYS),
        (_with(character_end_times_seconds=[0.128]), "alignment arrays differ in length"),
        (
            {"characters": [], "character_start_times_seconds": [], "character_end_times_seconds": []},
            "alignment is empty",
        ),
        (_with(characters=["I", 7]), "alignment characters must be strings"),
        (_with(characters=["I", True]), "alignment characters must be strings"),
        (_with(character_start_times_seconds=[-0.5, 0.1]), TIMES),
        (_with(character_end_times_seconds=[0.1, -1]), TIMES),
        (_with(character_start_times_seconds=[True, 0.1]), TIMES),
        (_with(character_start_times_seconds=["0.1", 0.1]), TIMES),
        (_with(character_start_times_seconds=[None, 0.1]), TIMES),
        (_with(character_start_times_seconds=[float("nan"), 0.1]), TIMES),
        (_with(character_end_times_seconds=[0.1, float("inf")]), TIMES),
        (_with(character_end_times_seconds=[0.1, 10**400]), TIMES),
    ],
)
def test_rejected_with_exact_reason(value, reason):
    assert accept_alignment(value) == reason
