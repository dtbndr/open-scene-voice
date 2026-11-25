import json

import pytest

from scenevoice.web import FIXED_FAILURE, failure_from_events, parse_event_line
from scenevoice.web.parse_plan_failure import FALLBACK, parse_plan_failure
from scenevoice.web.plan_problem import PlanProblem

TEMP = "/tmp/launch/check-abc123.md"


def fail(message, *, line=None, kind="invalid_input", event="fail"):
    return json.dumps(
        {"command": "plan", "event": event, "message": message, "kind": kind, "scene": None, "line": line, "status": None}
    )


def parse(*lines, temp=TEMP):
    return parse_plan_failure("\n".join(lines) + "\n", temp)


def test_the_prefix_and_the_matching_line_suffix_are_removed_and_the_line_is_kept():
    assert parse(fail(f"{TEMP}: Scene one is empty (line 4)", line=4)) == PlanProblem(4, "Scene one is empty")


def test_a_suffix_is_kept_when_the_event_line_differs_or_is_absent():
    assert parse(fail(f"{TEMP}: Odd (line 4)", line=5)) == PlanProblem(5, "Odd (line 4)")
    assert parse(fail(f"{TEMP}: Odd (line 4)", line=None)) == PlanProblem(None, "Odd (line 4)")


def test_a_null_line_is_kept_null():
    assert parse(fail(f"{TEMP}: Too long")) == PlanProblem(None, "Too long")


def test_the_last_invalid_input_event_wins_and_noise_lines_are_skipped():
    lines = [
        "not json",
        "[1, 2]",
        '"text"',
        fail(f"{TEMP}: first", line=1),
        json.dumps({"command": "plan", "event": "note", "message": "n"}),
        fail(f"{TEMP}: second", line=2),
        "{broken",
    ]
    assert parse(*lines) == PlanProblem(2, "second")


def test_stderr_is_split_on_newline_only_so_a_unicode_separator_inside_a_string_survives():
    text = fail(f"{TEMP}: a b\u0085c", line=None).replace("\\u2028", " ").replace("\\u0085", "\u0085")
    assert " " in text
    assert parse(text) == PlanProblem(None, "a b\u0085c")


def test_an_absent_prefix_gives_the_fixed_sentence_and_never_the_event_message():
    problem = parse(fail("/other/place.md: secret detail", line=3))
    assert problem == PlanProblem(3, FALLBACK)
    assert "secret" not in problem.message and "/other" not in problem.message


def test_the_prefix_must_be_exact_and_at_the_start():
    assert parse(fail(f"x {TEMP}: y")).message == FALLBACK
    assert parse(fail(f"{TEMP}x: y")).message == FALLBACK


@pytest.mark.parametrize("kind", ["other", "provider_error", None])
def test_a_fail_of_another_kind_is_not_a_script_problem(kind):
    assert parse(fail(f"{TEMP}: x", kind=kind)) is None


def test_a_last_fail_of_another_kind_is_not_hidden_by_an_earlier_script_problem():
    assert parse(fail(f"{TEMP}: x"), fail(f"{TEMP}: y", kind="other")) is None


def test_a_cannot_read_file_message_is_the_servers_fault():
    assert parse(fail(f"{TEMP}: cannot read file (No such file or directory)")) is None


def test_no_events_or_only_non_fail_events_give_none():
    assert parse_plan_failure("", TEMP) is None
    assert parse(json.dumps({"event": "ok", "message": "m"})) is None


def test_a_non_string_message_or_a_boolean_line_does_not_crash():
    assert parse(json.dumps({"event": "fail", "kind": "invalid_input", "message": 5, "line": 1})) is None
    assert parse(fail(f"{TEMP}: x (line 1)", line=True)) == PlanProblem(None, "x (line 1)")


def fail_failure_from_events(kind: str, message: str = "m", scene: int | None = None, status: int | None = None) -> dict[str, object]:
    return {"type": "fail", "kind": kind, "message": message, "scene": scene, "line": None, "status": status}


NOTE = {"type": "note", "message": "n"}
RUN_FAILURE = "SceneVoice stopped with an error before the job was finished."


def test_the_last_fail_event_wins() -> None:
    events = [fail_failure_from_events("quota", scene=1), NOTE, fail_failure_from_events("bad_key", scene=2, status=401), NOTE]
    got = failure_from_events(events, outcome="failed", message=RUN_FAILURE)
    assert got == {"kind": "bad_key", "message": FIXED_FAILURE, "scene": 2, "status": 401}


@pytest.mark.parametrize("kind", ["rate_limited", "", "QUOTA"])
def test_a_kind_outside_the_six_becomes_other(kind: str) -> None:
    got = failure_from_events([fail_failure_from_events(kind)], outcome="failed", message=RUN_FAILURE)
    assert got is not None
    assert got["kind"] == "other"


def test_only_invalid_input_carries_the_childs_message() -> None:
    got = failure_from_events([fail_failure_from_events("invalid_input", "Scene 2 is empty.")], outcome="failed", message=RUN_FAILURE)
    assert got == {"kind": "invalid_input", "message": "Scene 2 is empty.", "scene": None, "status": None}
    other = failure_from_events([fail_failure_from_events("provider_down", "raw provider text")], outcome="failed", message=RUN_FAILURE)
    assert other is not None
    assert other["message"] == FIXED_FAILURE


def test_an_invalid_input_with_no_message_gets_the_fixed_message() -> None:
    got = failure_from_events([fail_failure_from_events("invalid_input", "")], outcome="failed", message=RUN_FAILURE)
    assert got is not None
    assert got["message"] == FIXED_FAILURE


def test_a_failed_exit_with_no_fail_event_is_other_with_the_fixed_message() -> None:
    expected = {"kind": "other", "message": FIXED_FAILURE, "scene": None, "status": None}
    assert failure_from_events([NOTE], outcome="failed", message=RUN_FAILURE) == expected
    assert failure_from_events([], outcome="failed", message=RUN_FAILURE) == expected


def test_a_message_a_hook_chose_stays_and_is_other_whatever_the_events_say() -> None:
    got = failure_from_events([fail_failure_from_events("quota")], outcome="failed", message="Your earlier audio could not be put back.")
    assert got == {"kind": "other", "message": "Your earlier audio could not be put back.", "scene": None, "status": None}


@pytest.mark.parametrize("outcome", ["done", "cancelled", "running"])
def test_only_a_failed_job_has_a_failure(outcome: str) -> None:
    assert failure_from_events([fail_failure_from_events("quota")], outcome=outcome, message=None) is None


@pytest.mark.parametrize(
    "internal", ["SceneVoice could not finish the job.", "SceneVoice could not start the job."]
)
def test_the_runners_own_internal_texts_never_reach_the_user(internal: str) -> None:
    got = failure_from_events([fail_failure_from_events("quota")], outcome="failed", message=internal)
    assert got == {"kind": "other", "message": "SceneVoice could not finish. Try again.", "scene": None, "status": None}


def test_the_approved_fixed_wording_is_exactly_this_text() -> None:
    assert FIXED_FAILURE == "SceneVoice could not finish. Try again."
    got = failure_from_events([], outcome="failed", message=RUN_FAILURE)
    assert got is not None
    assert got["message"] == "SceneVoice could not finish. Try again."


def line(**fields: object) -> str:
    return json.dumps(fields)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            line(command="synth", event="scene", message="m", state="done", scene=2, total=3, path="audio/002.wav"),
            {
                "type": "scene",
                "command": "synth",
                "message": "m",
                "state": "done",
                "scene": 2,
                "total": 3,
                "path": "audio/002.wav",
            },
        ),
        (line(command="align", event="note", message="n"), {"type": "note", "command": "align", "message": "n"}),
        (
            line(command="synth", event="fail", message="f", kind="quota", scene=2, line=5, status=429),
            {"type": "fail", "command": "synth", "message": "f", "kind": "quota", "scene": 2, "line": 5, "status": 429},
        ),
    ],
)
def test_each_of_the_four_events_keeps_only_its_allowlisted_fields(text: str, expected: dict[str, object]) -> None:
    assert parse_event_line(text) == expected


def test_fields_outside_the_allowlist_are_dropped() -> None:
    parsed = parse_event_line(
        line(command="synth", event="note", message="n", traceback="x", path="audio/001.wav", scene=4, extra={"a": 1})
    )
    assert parsed == {"type": "note", "command": "synth", "message": "n"}
    fail = parse_event_line(line(command="synth", event="fail", message="f", kind="quota", total=9, state="done"))
    assert fail == {
        "type": "fail",
        "command": "synth",
        "message": "f",
        "kind": "quota",
        "scene": None,
        "line": None,
        "status": None,
    }


@pytest.mark.parametrize(
    "text",
    [
        "Traceback (most recent call last):",
        "usage: scenevoice synth [-h]",
        line(command="synth", event="start", message="unknown"),
        line(command="synth", event="scene", message="m", state="running", scene=1, total=2),
    ],
)
def test_a_line_that_is_not_a_known_event_object_is_dropped_whole(text: str) -> None:
    assert parse_event_line(text) is None


@pytest.mark.parametrize(
    "path",
    ["audio/1.wav", "../audio/001.wav", "/tmp/audio/001.wav"],
)
# Read outside the project: the path later feeds the audio route, so only audio/NNN.wav survives.
def test_a_path_that_is_not_audio_nnn_wav_is_left_out(path: object) -> None:
    parsed = parse_event_line(line(command="synth", event="scene", message="m", state="done", scene=1, total=1, path=path))
    assert parsed is not None
    assert "path" not in parsed


@pytest.mark.parametrize("value", [True, "3"])
def test_a_value_that_is_not_a_plain_integer_becomes_null(value: object) -> None:
    scene = parse_event_line(line(command="synth", event="scene", message="m", state="done", scene=value, total=value))
    assert scene is not None
    assert (scene["scene"], scene["total"]) == (None, None)
    fail = parse_event_line(
        line(command="synth", event="fail", message="f", kind="other", scene=value, line=value, status=value)
    )
    assert fail is not None
    assert (fail["scene"], fail["line"], fail["status"]) == (None, None, None)


@pytest.mark.parametrize("kind", ["rate_limited"])
def test_a_failure_kind_outside_the_six_becomes_other(kind: object) -> None:
    parsed = parse_event_line(line(command="synth", event="fail", message="f", kind=kind))
    assert parsed is not None
    assert parsed["kind"] == "other"


@pytest.mark.parametrize("command", ["rm"])
def test_an_unknown_command_is_null_and_a_non_text_message_is_empty(command: object) -> None:
    parsed = parse_event_line(line(command=command, event="note", message=7))
    assert parsed == {"type": "note", "command": None, "message": ""}
