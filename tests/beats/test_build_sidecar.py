"""Building and serialising the canonical beats sidecar, its script hash and freshness check (WS35 decision 7)."""

import copy
import hashlib
import json
from typing import Any

import pytest
from paths_helper import FIXTURES

from scenevoice.beats.build_sidecar import build_sidecar
from scenevoice.beats.check_beats_coverage import check_beats_coverage
from scenevoice.beats.check_beats_fresh import check_beats_fresh
from scenevoice.beats.check_sidecar_shape import check_sidecar_shape
from scenevoice.beats.clean_beats_reply import clean_beats_reply
from scenevoice.beats.hash_script_bytes import hash_script_bytes
from scenevoice.beats.parse_beats_reply import parse_beats_reply
from scenevoice.beats.segment_scenes import segment_scenes
from scenevoice.beats.serialise_sidecar import serialise_sidecar
from scenevoice.validation.load_scenes import load_scenes
from scenevoice.validation.scene import Scene

_FIXTURE = FIXTURES / "openrouter" / "beats_synthetic_cases.json"


_CASES: dict[str, dict[str, Any]] = json.loads(_FIXTURE.read_text(encoding="utf-8"))["cases"]


_VALID = [n for n, c in _CASES.items() if c["expect"]["stage"] == "ok"]


_SCRIPT = "## Café ☕\nOne. Two.\n\n## Empty\n".encode()


def _scenes() -> list[Scene]:
    return [Scene(1, "Café ☕", "One. Two.", 2), Scene(2, "Empty", "", 4)]


def _parsed(note: str = "  a shot \n") -> list[dict[str, Any]]:
    return [
        {"scene": 1, "title": "Reply Title", "beats": [{"first": 1, "last": 2, "note": note}]},
        {"scene": 2, "beats": []},
    ]


def test_build_sidecar_exact_document():
    doc = build_sidecar(_SCRIPT, _scenes(), [2, 0], _parsed())
    assert doc == {
        "version": 1,
        "script_sha256": hash_script_bytes(_SCRIPT),
        "scenes": [
            {
                "ordinal": 1,
                "title": "Café ☕",
                "segment_count": 2,
                "beats": [{"first": 1, "last": 2, "note": "a shot"}],
            },
            {"ordinal": 2, "title": "Empty", "segment_count": 0, "beats": []},
        ],
    }
    assert check_sidecar_shape(doc) is None
    assert list(doc) == ["version", "script_sha256", "scenes"]
    assert list(doc["scenes"][0]) == ["ordinal", "title", "segment_count", "beats"]
    assert list(doc["scenes"][0]["beats"][0]) == ["first", "last", "note"]


def test_title_and_ordinal_come_from_script_not_reply():
    doc = build_sidecar(_SCRIPT, _scenes(), [2, 0], _parsed())
    assert doc["scenes"][0]["title"] == "Café ☕"  # reply said "Reply Title"
    assert "scene" not in doc["scenes"][0]


def test_segment_count_comes_from_counts_not_reply_beats():
    parsed = [{"scene": 1, "beats": [{"first": 1, "last": 2, "note": "n"}]}, {"scene": 2, "beats": []}]
    doc = build_sidecar(_SCRIPT, _scenes(), [2, 0], parsed)
    assert [s["segment_count"] for s in doc["scenes"]] == [2, 0]


def test_build_does_not_mutate_parsed():
    parsed = _parsed()
    before = json.dumps(parsed, sort_keys=True)
    build_sidecar(_SCRIPT, _scenes(), [2, 0], parsed)
    assert json.dumps(parsed, sort_keys=True) == before


def test_serialise_exact_text_non_ascii_two_space_trailing_newline():
    doc = build_sidecar(_SCRIPT, _scenes(), [2, 0], _parsed())
    digest = hash_script_bytes(_SCRIPT)
    expected = (
        "{\n"
        '  "version": 1,\n'
        f'  "script_sha256": "{digest}",\n'
        '  "scenes": [\n'
        "    {\n"
        '      "ordinal": 1,\n'
        '      "title": "Café ☕",\n'
        '      "segment_count": 2,\n'
        '      "beats": [\n'
        "        {\n"
        '          "first": 1,\n'
        '          "last": 2,\n'
        '          "note": "a shot"\n'
        "        }\n"
        "      ]\n"
        "    },\n"
        "    {\n"
        '      "ordinal": 2,\n'
        '      "title": "Empty",\n'
        '      "segment_count": 0,\n'
        '      "beats": []\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )
    text = serialise_sidecar(doc)
    assert text == expected
    assert text.endswith("}\n") and not text.endswith("\n\n")
    assert "\\u" not in text
    assert json.loads(text) == doc


def test_serialise_keeps_dict_key_order_not_sorted():
    text = serialise_sidecar({"version": 1, "script_sha256": "x", "scenes": []})
    assert text == '{\n  "version": 1,\n  "script_sha256": "x",\n  "scenes": []\n}\n'


@pytest.mark.parametrize("name", _VALID)
def test_chain_fixture_case_to_fresh_sidecar(name):
    case = _CASES[name]
    if case["script"] is None:
        script_bytes = b"## One\nA. B.\n\n## Two\n"
        scenes = [Scene(1, "One", "A. B.", 2), Scene(2, "Two", "", 4)]
    else:
        script_bytes = case["script"].encode("utf-8")
        loaded = load_scenes(script_bytes)
        assert isinstance(loaded, list)
        scenes = loaded
    counts = [len(s) for s in segment_scenes(scenes)]
    assert counts == case["segment_counts"]
    cleaned, _ = clean_beats_reply(case["reply"])
    parsed, problem = parse_beats_reply(cleaned)
    assert problem is None and parsed is not None
    assert check_beats_coverage(counts, parsed) == []
    doc = build_sidecar(script_bytes, scenes, counts, parsed)
    assert check_sidecar_shape(doc) is None
    assert [s["title"] for s in doc["scenes"]] == [s.title for s in scenes]
    text = serialise_sidecar(doc)
    assert json.loads(text) == doc
    assert check_beats_fresh(script_bytes, json.loads(text)) is None
    assert check_beats_fresh(script_bytes + b"x", json.loads(text)) is not None


SCRIPT = b"# Scene one\n\nHello there.\n"


def sidecar_for(script: bytes) -> dict[str, Any]:
    return {
        "version": 1,
        "script_sha256": hashlib.sha256(script).hexdigest(),
        "scenes": [
            {
                "ordinal": 1,
                "title": "Opening",
                "segment_count": 2,
                "beats": [{"first": 1, "last": 2, "note": "wide shot"}],
            }
        ],
    }


@pytest.mark.parametrize("data", ["café — 日本".encode()])
def test_hash_script_bytes_is_sha256_hexdigest(data: bytes) -> None:
    assert hash_script_bytes(data) == hashlib.sha256(data).hexdigest()


def test_fresh_when_hash_matches_and_shape_valid() -> None:
    assert check_beats_fresh(SCRIPT, sidecar_for(SCRIPT)) is None


def test_stale_when_one_byte_changes() -> None:
    reason = check_beats_fresh(SCRIPT.replace(b"Hello", b"Jello"), sidecar_for(SCRIPT))
    assert isinstance(reason, str) and reason


def test_stale_when_only_trailing_newline_differs() -> None:
    reason = check_beats_fresh(SCRIPT + b"\n", sidecar_for(SCRIPT))
    assert isinstance(reason, str) and reason


def test_malformed_sidecar_returns_the_shape_message() -> None:
    doc = sidecar_for(SCRIPT)
    del doc["scenes"]
    expected = check_sidecar_shape(copy.deepcopy(doc))
    assert expected is not None
    assert check_beats_fresh(SCRIPT, doc) == expected


@pytest.mark.parametrize("bad", [None, []])
def test_non_mapping_sidecar_returns_reason_without_raising(bad: object) -> None:
    reason = check_beats_fresh(SCRIPT, bad)
    assert isinstance(reason, str) and reason
