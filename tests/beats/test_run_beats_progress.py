"""run_beats --progress json: note, ok and fail events with kinds; no scene events (text unchanged)."""

import io
import json

import pytest
from beats_run_helper import GOOD, SCRIPT, canonical, fail_write, replying, run
from chat_run_helper import KEY, FakeChat

from scenevoice.beats import run_beats
from scenevoice.beats.make_beats_say import make_beats_say
from scenevoice.openrouter import (
    ChatBlocked,
    ChatError,
    ChatOutOfLength,
    ChatTimedOut,
    ChatUnreachable,
    ChatUnreadable,
)


@pytest.fixture(autouse=True)
def _offline_clean_env(clean_env, no_sockets):
    """Every test here runs run_beats on real files: empty cwd, no key in env, no sockets."""


def run_json(tmp_path, fake, script=SCRIPT, env=None, out=None, script_path=None):
    script_path = script_path or tmp_path / "script.md"
    if script is not None:
        script_path.write_bytes(script)
    out = out or tmp_path / "beats.json"
    err, std = io.StringIO(), io.StringIO()
    code = run_beats(
        script_path,
        out,
        "synthetic/model",
        {"OPENROUTER_API_KEY": KEY} if env is None else env,
        tmp_path / "dotenv",
        fake.factory,
        err,
        std,
        progress_mode="json",
    )
    lines = err.getvalue().splitlines()
    return code, [json.loads(line) for line in lines], std.getvalue(), out


def only_fail(events):
    assert [e["event"] for e in events] == ["fail"]
    assert {e["command"] for e in events} == {"beats"}
    return events[0]


def test_success_gives_cleaned_note_then_one_ok_and_no_scene_events(tmp_path):
    fenced = "```json\n" + json.dumps(GOOD) + "\n```"
    code, events, stdout, out = run_json(tmp_path, replying(fenced))
    assert code == 0 and stdout == ""
    assert [e["event"] for e in events] == ["note", "ok"]
    assert events[0]["message"] == "cleaned: removed a code fence around the whole reply"
    assert events[1]["message"] == f"{out} (2 scenes, 2 beats)"


def test_success_without_cleaning_is_a_single_ok(tmp_path):
    code, events, _, _ = run_json(tmp_path, replying(GOOD))
    assert code == 0
    assert [e["event"] for e in events] == ["ok"]


def test_http_status_chat_error_carries_kind_and_status(tmp_path):
    code, events, _, out = run_json(tmp_path, FakeChat(ChatError(402, "no credit")))
    assert code == 1 and not out.exists()
    fail = only_fail(events)
    assert (fail["kind"], fail["status"]) == ("quota", 402)
    assert fail["message"] == "the OpenRouter account has no credit left"


@pytest.mark.parametrize("error", [ChatTimedOut(None, "t"), ChatUnreachable(None, "reset")])
def test_transport_chat_errors_are_provider_down_with_null_status(tmp_path, error):
    _, events, _, _ = run_json(tmp_path, FakeChat(error))
    fail = only_fail(events)
    assert (fail["kind"], fail["status"]) == ("provider_down", None)


@pytest.mark.parametrize("error", [ChatUnreadable(200, "x"), ChatBlocked(200, "x"), ChatOutOfLength(200, "x")])
def test_subclass_chat_errors_are_other_and_pass_the_status_through(tmp_path, error):
    _, events, _, _ = run_json(tmp_path, FakeChat(error))
    fail = only_fail(events)
    assert (fail["kind"], fail["status"]) == ("other", 200)


def test_missing_script_is_invalid_input(tmp_path):
    fake = replying(GOOD)
    code, events, _, _ = run_json(tmp_path, fake, script=None, script_path=tmp_path / "nope.md")
    assert code == 1 and fake.keys == []
    fail = only_fail(events)
    assert (fail["kind"], fail["status"]) == ("invalid_input", None)


def test_existing_out_file_is_invalid_input(tmp_path):
    out = tmp_path / "beats.json"
    out.write_text("old")
    fake = replying(GOOD)
    code, events, _, _ = run_json(tmp_path, fake, out=out)
    assert code == 1 and fake.keys == [] and out.read_text() == "old"
    assert only_fail(events)["kind"] == "invalid_input"


def test_missing_key_is_missing_key_kind(tmp_path):
    fake = replying(GOOD)
    code, events, _, _ = run_json(tmp_path, fake, env={})
    assert code == 1 and fake.keys == []
    assert only_fail(events)["kind"] == "missing_key"


def test_write_failure_after_reply_is_other_and_text_still_goes_to_stdout(tmp_path, monkeypatch):
    fail_write(monkeypatch)
    code, events, stdout, _ = run_json(tmp_path, replying(GOOD))
    assert code == 1
    assert stdout == canonical()
    assert only_fail(events)["kind"] == "other"


def test_written_but_invalid_reply_gives_one_other_fail_per_problem(tmp_path):
    raw = json.dumps(GOOD)
    code, events, _, _ = run_json(tmp_path, replying(raw, finish="length"))
    assert code == 1
    assert [e["event"] for e in events] == ["fail"]
    assert events[0]["kind"] == "other"
    assert "written, but the model stopped at its length limit" in events[0]["message"]

    bad = json.dumps({"scenes": [GOOD["scenes"][0]]})
    _, events, _, _ = run_json(tmp_path, replying(bad), out=tmp_path / "b2.json")
    assert [(e["event"], e["kind"]) for e in events] == [("fail", "other")]


def test_two_problems_give_two_fail_events(tmp_path):
    raw = json.dumps({"scenes": [GOOD["scenes"][0]]})
    _, events, _, _ = run_json(tmp_path, replying(raw, finish="length"))
    assert [(e["event"], e["kind"]) for e in events] == [("fail", "other")] * 2


def test_key_in_a_chat_error_never_reaches_a_json_line(tmp_path):
    error = ChatError(400, f"bad request for {KEY}")
    code, events, _, _ = run_json(tmp_path, FakeChat(error))
    assert code == 1
    assert KEY not in json.dumps(events)
    assert "[redacted]" in only_fail(events)["message"]


def test_text_mode_is_unchanged(tmp_path):
    code, err, out = run(tmp_path, replying(GOOD))
    assert code == 0
    assert err == f"scenevoice beats: OK {out} (2 scenes, 2 beats)\n"


@pytest.mark.parametrize(
    "error", [ChatBlocked(503, "x"), ChatUnreadable(402, "x"), ChatOutOfLength(429, "x")]
)
def test_subclass_beats_a_status_that_would_map_elsewhere(tmp_path, error):
    _, events, _, _ = run_json(tmp_path, FakeChat(error))
    fail = only_fail(events)
    assert (fail["kind"], fail["status"]) == ("other", error.status)


def test_json_say_redacts_a_secret_that_was_not_pre_redacted():
    err = io.StringIO()
    say = make_beats_say(err, [KEY], progress_mode="json")
    say(f"FAIL could not write, saw {KEY} here", kind="other", status=None)
    assert KEY not in err.getvalue()
    assert "[redacted]" in json.loads(err.getvalue())["message"]
