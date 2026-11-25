"""Cleaning, parsing and coverage of a beats reply (WS35 decisions 5, 6 and 7).

Every reply here is synthetic and UNOBSERVED: no model produced it. The cases
live in tests/fixtures/openrouter/beats_synthetic_cases.json, which is marked
unobserved with a refresh note; refresh them from the paid probe and at M14.
"""

import json
from typing import Any

import pytest
from paths_helper import FIXTURES

from scenevoice.beats.check_beats_coverage import check_beats_coverage
from scenevoice.beats.clean_beats_reply import clean_beats_reply
from scenevoice.beats.parse_beats_reply import parse_beats_reply

_FIXTURE = FIXTURES / "openrouter" / "beats_synthetic_cases.json"
_DATA = json.loads(_FIXTURE.read_text(encoding="utf-8"))
_CASES: dict[str, dict[str, Any]] = _DATA["cases"]


# One case per equivalence class of the P1 rules "a reply that does not cover the
# script exactly is written raw and fails" and "a paid reply whose scenes are
# malformed is written raw and fails, never crashes"; type-confusion variants collapse.
# The last three pin the per-scene branches of parse_beats_reply: a scene key check
# (extra_scene_key shares that branch with sidecar_key_ordinal_rejected, so it is left
# out), scene must be an object, beats must be a list.
_KEPT = [
    "valid", "valid_in_code_fence", "valid_with_bom", "one_scene_of_two", "extra_scene",
    "wrong_scene_number", "scenes_out_of_order", "sentence_covered_twice", "gap_between_beats",
    "gap_at_end", "range_past_last_sentence", "empty_beats_for_scene_with_sentences",
    "empty_scene_with_empty_beats", "empty_scene_with_beats", "blank_note", "multiline_note",
    "overlong_note", "boolean_as_first", "non_json_text", "json_array", "truncated_reply",
    "extra_top_level_key", "missing_scenes_key", "scenes_not_a_list",
    "sidecar_key_ordinal_rejected", "scene_not_an_object", "beats_not_a_list",
]


def _run(case: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    """Return (stage reached, cleaned labels, problems) for one fixture case."""
    cleaned, labels = clean_beats_reply(case["reply"])
    parsed, problem = parse_beats_reply(cleaned)
    if problem is not None:
        return "parse", labels, [problem]
    assert parsed is not None
    problems = check_beats_coverage(case["segment_counts"], parsed)
    return ("coverage" if problems else "ok"), labels, problems


@pytest.mark.parametrize("name", _KEPT)
def test_fixture_case_outcome(name):
    """Unobserved synthetic reply: stage, problem count, scene named, message."""
    case, expect = _CASES[name], _CASES[name]["expect"]
    stage, labels, problems = _run(case)
    assert stage == expect["stage"], problems
    assert len(problems) == expect["problem_count"], problems
    assert labels == expect["cleaned_labels"]
    if expect["scene"] is not None:
        assert f"scene {expect['scene']}" in problems[0]
    if expect["message_contains"] is not None:
        assert expect["message_contains"] in problems[0]
    for problem in problems:
        assert "\n" not in problem


def test_clean_strips_bom_and_one_wrapping_fence_only():
    text, labels = clean_beats_reply("﻿```json\n{\"a\": 1}\n```\n")
    assert text == '{"a": 1}'
    assert labels == [
        "removed a leading byte order mark",
        "removed a code fence around the whole reply",
    ]


def test_clean_leaves_everything_else_alone():
    raw = '  {"a":\t1}\r\n'
    assert clean_beats_reply(raw) == (raw, [])


def test_clean_does_not_strip_a_fence_that_does_not_wrap_the_reply():
    raw = 'Here:\n```json\n{"a": 1}\n```\n'
    assert clean_beats_reply(raw) == (raw, [])


def test_parse_returns_per_scene_beats():
    reply = '{"scenes":[{"scene":1,"beats":[{"first":1,"last":2,"note":"a"}]}]}'
    parsed, problem = parse_beats_reply(reply)
    assert problem is None
    assert parsed == [{"scene": 1, "beats": [{"first": 1, "last": 2, "note": "a"}]}]


def test_parse_reports_the_cut_off_position():
    parsed, problem = parse_beats_reply('{"scenes": [{"scene": 1, "bea')
    assert parsed is None
    assert problem is not None and problem.startswith("the reply is not valid JSON")


def test_coverage_names_every_missing_scene():
    problems = check_beats_coverage([1, 1, 1], [{"scene": 1, "beats": [
        {"first": 1, "last": 1, "note": "a"}]}])
    assert problems == ["scene 2 is missing from the reply", "scene 3 is missing from the reply"]


# P1 rule "a missed unwrap wastes a paid call" (decision G): leading blank lines
# before a wrapping fence, and prose after the closing fence, must not defeat it.
def test_clean_unwraps_after_blank_lines_and_drops_trailing_text():
    text, labels = clean_beats_reply('\n\n```json\n{"a": 1}\n```\nHope this helps!\n')
    assert text == '{"a": 1}'
    assert labels == [
        "removed a code fence around the whole reply",
        "dropped text after the closing code fence",
    ]


def test_clean_leaves_blank_lines_then_no_fence_unchanged():
    raw = '\n\n{"a": 1}\n'
    assert clean_beats_reply(raw) == (raw, [])


def test_clean_leaves_blank_lines_then_unclosed_fence_unchanged():
    raw = '\n```json\n{"a": 1}\n'
    assert clean_beats_reply(raw) == (raw, [])


_REAL_REPLY = FIXTURES / "openrouter" / "beats_real_reply_2026-11-25.json"
_REAL_SCRIPT = (
    "## Opening\n"
    "Welcome back to the channel. Today we are unboxing a small camera that fits in a coat pocket.\n\n"
    "## First look\n"
    "The body is light, the grip is rubberised, and the lens cap clicks on with a satisfying snap.\n\n"
    "## Verdict\n"
    "For the price it is a great little camera. Thanks for watching, and see you next time.\n"
)


def test_real_provider_reply_judges_valid(tmp_path):
    """P1 provider fact: a real reply (observed 2026-11-25, openai/gpt-6-luna) parses clean.

    A paid beats call must not be wasted on a reply shape the product rejects.
    """
    from scenevoice.beats.judge_beats_reply import judge_beats_reply
    from scenevoice.beats.read_beats_script import read_beats_script
    from scenevoice.beats.segment_scenes import segment_scenes
    from scenevoice.openrouter.parse_chat_response import parse_chat_response

    script = tmp_path / "short.txt"
    script.write_text(_REAL_SCRIPT, encoding="utf-8")
    read = read_beats_script(script)
    assert not isinstance(read, str), read
    script_bytes, scenes = read
    segments = segment_scenes(scenes)
    body = json.loads(_REAL_REPLY.read_text(encoding="utf-8"))["body"]
    reply, truncated = parse_chat_response(json.dumps(body).encode("utf-8"))
    cleaned, _labels = clean_beats_reply(reply)
    text, problems, beat_count = judge_beats_reply(cleaned, truncated, script_bytes, scenes, segments)
    assert problems == []
    assert [len(s) for s in segments] == [2, 1, 2]
    assert beat_count == 5
    assert json.loads(text)["scenes"][0]["beats"][0]["first"] == 1
