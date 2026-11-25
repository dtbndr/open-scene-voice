"""Pins the beats sidecar schema (version 1, WS35 decision 7)."""

import copy
from typing import Any

import pytest

from scenevoice.beats import check_sidecar_shape

HASH = "a" * 64


def good() -> dict[str, Any]:
    return {
        "version": 1,
        "script_sha256": HASH,
        "scenes": [
            {
                "ordinal": 1,
                "title": "Opening",
                "segment_count": 5,
                "beats": [
                    {"first": 1, "last": 2, "note": "wide shot"},
                    {"first": 3, "last": 5, "note": "close up"},
                ],
            },
            {"ordinal": 2, "title": "Empty", "segment_count": 0, "beats": []},
        ],
    }


def mutated(fn: Any) -> Any:
    doc = copy.deepcopy(good())
    result = fn(doc)
    return doc if result is None else result


def beat(doc: dict[str, Any], i: int = 0) -> dict[str, Any]:
    b: dict[str, Any] = doc["scenes"][0]["beats"][i]
    return b


def scene(doc: dict[str, Any], i: int = 0) -> dict[str, Any]:
    s: dict[str, Any] = doc["scenes"][i]
    return s


def test_valid_sidecar_passes() -> None:
    assert check_sidecar_shape(good()) is None


def _set(d: dict[str, Any], k: str, v: Any) -> None:
    d[k] = v


def _del(d: dict[str, Any], k: str) -> None:
    del d[k]


CASES: list[tuple[str, Any, str]] = [
    ("version_wrong", lambda d: _set(d, "version", 2), "version"),
    ("version_missing", lambda d: _del(d, "version"), "version"),
    ("version_bool", lambda d: _set(d, "version", True), "version"),
    ("hash_short", lambda d: _set(d, "script_sha256", "a" * 63), "script_sha256"),
    ("hash_upper", lambda d: _set(d, "script_sha256", "A" * 64), "script_sha256"),
    ("hash_nonhex", lambda d: _set(d, "script_sha256", "g" * 64), "script_sha256"),
    ("top_extra", lambda d: _set(d, "model", "x"), "model"),
    ("scenes_missing", lambda d: _del(d, "scenes"), "scenes"),
    ("scenes_type", lambda d: _set(d, "scenes", {}), "scenes"),
    ("scene_not_mapping", lambda d: d["scenes"].__setitem__(0, []), "scenes[1]"),
    ("ordinal_wrong", lambda d: _set(scene(d, 1), "ordinal", 3), "ordinal"),
    ("title_missing", lambda d: _del(scene(d), "title"), "title"),
    ("count_negative", lambda d: _set(scene(d), "segment_count", -1), "segment_count"),
    ("count_missing", lambda d: _del(scene(d), "segment_count"), "segment_count"),
    ("beats_missing", lambda d: _del(scene(d), "beats"), "beats"),
    ("beats_type", lambda d: _set(scene(d), "beats", "x"), "beats"),
    ("beat_not_mapping", lambda d: scene(d)["beats"].__setitem__(0, 1), "beats[1]"),
    ("beat_extra", lambda d: _set(beat(d), "x", 1), "beats[1]"),
    ("first_missing", lambda d: _del(beat(d), "first"), "first"),
    ("first_gt_last", lambda d: beat(d).update(first=3, last=2), "first"),
    ("first_zero", lambda d: _set(beat(d), "first", 0), "first"),
    ("last_over_count", lambda d: _set(beat(d, 1), "last", 6), "last"),
    ("first_bool", lambda d: _set(beat(d), "first", True), "first"),
    ("gap", lambda d: _set(beat(d, 1), "first", 4), "first"),
    ("overlap", lambda d: _set(beat(d, 1), "first", 2), "first"),
    ("first_beat_not_1", lambda d: beat(d).update(first=2, last=2), "first"),
    ("last_short", lambda d: _set(beat(d, 1), "last", 4), "last"),
    ("zero_count_nonempty", lambda d: _set(scene(d, 1), "beats", [{"first": 1, "last": 1, "note": "n"}]), "beats"),
    ("count_positive_empty", lambda d: _set(scene(d), "beats", []), "beats"),
    ("note_blank", lambda d: _set(beat(d), "note", "   "), "note"),
    ("note_newline", lambda d: _set(beat(d), "note", "a\nb"), "note"),
    ("note_201", lambda d: _set(beat(d), "note", "x" * 201), "note"),
    ("note_surrogate", lambda d: _set(beat(d), "note", "a\ud800b"), "note"),
    ("note_type", lambda d: _set(beat(d), "note", 5), "note"),
]


@pytest.mark.parametrize("name,fn,field", CASES, ids=[c[0] for c in CASES])
def test_invalid_names_field(name: str, fn: Any, field: str) -> None:
    msg = check_sidecar_shape(mutated(fn))
    assert msg is not None
    assert "\n" not in msg
    assert field in msg


def test_segment_count_and_empty_beats_messages_name_their_field() -> None:
    negative = mutated(lambda d: _set(scene(d), "segment_count", -1))
    assert check_sidecar_shape(negative) == "scenes[1].segment_count must be a non-negative integer"
    empty = mutated(lambda d: _set(scene(d), "beats", []))
    assert check_sidecar_shape(empty) == "scenes[1].beats must not be empty when segment_count is 5"


def test_note_of_200_chars_passes() -> None:
    doc = good()
    beat(doc)["note"] = "x" * 200
    assert check_sidecar_shape(doc) is None


@pytest.mark.parametrize("doc", [None, []])
def test_non_mapping_input(doc: Any) -> None:
    msg = check_sidecar_shape(doc)
    assert msg is not None and "\n" not in msg


def test_never_raises_on_hostile_input() -> None:
    class Weird:
        def __eq__(self, other: object) -> bool:
            raise RuntimeError

    assert check_sidecar_shape({"version": Weird()}) is not None
    assert check_sidecar_shape({1: 2}) is not None
