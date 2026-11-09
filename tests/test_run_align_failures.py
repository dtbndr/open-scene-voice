import io
import json
import os

import pytest
from align_run_helper import (
    ENV,
    HELLO,
    KEY,
    PREFIX,
    Fake,
    NoTerminal,
    body,
    fail_with,
    go,
    pack_dir,
)

from scenevoice.align.run_align import run_align

NOPE = body([(" nope", 0.1)])
EXISTING = b'{"scenes": []}\n'


def test_notes_in_scene_then_line_order_before_ok(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Zebra yak. Quartz.", "Hello there. Mango."])
    fake = Fake([NOPE, body(HELLO)])
    code, err, _ = go(plan_path, out, fake, tmp_path)
    assert code == 0
    assert err.splitlines() == [
        PREFIX + "NOTE no synth_record.json, all scenes transcribed",
        PREFIX + "NOTE scene 1 line 1: no match, start_ms null",
        PREFIX + "NOTE scene 1 line 2: no match, start_ms null",
        PREFIX + "NOTE scene 2 line 2: no match, start_ms null",
        PREFIX + "OK 2 scenes, 4 lines, 3 unmatched, 0 from synth record, 2 transcribed",
    ]


def test_check_8_failure_prints_notes_then_fail(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Zebra yak.", "Hello there."])
    (out / "line_timings.json").write_bytes(EXISTING)
    fake = Fake([NOPE, body(HELLO)])
    original = fake.__call__

    def lock_after_last_call(wav):
        result = original(wav)
        if len(fake.received) == 2:
            os.chmod(out, 0o500)
        return result

    err = io.StringIO()
    try:
        code = run_align(
            plan_path, NoTerminal(), ENV, tmp_path / "no.env", out, lambda k: lock_after_last_call, err
        )
    finally:
        os.chmod(out, 0o700)
    if code == 0:
        pytest.skip("directory permissions are not enforced here")
    assert code == 1
    lines = err.getvalue().splitlines()
    assert lines == [
        PREFIX + "NOTE no synth_record.json, all scenes transcribed",
        PREFIX + "NOTE scene 1 line 1: no match, start_ms null",
        PREFIX + "FAIL could not write line_timings.json",
    ]
    assert (out / "line_timings.json").read_bytes() == EXISTING
    assert sorted(p.name for p in out.iterdir()) == ["audio", "line_timings.json"]


def test_check_7_failure_prints_no_note(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Zebra yak.", "Hello there."])
    code, err, _ = go(plan_path, out, Fake([NOPE, fail_with(503, "down")]), tmp_path)
    assert code == 1
    assert err == f"{PREFIX}FAIL scene 2: provider error (HTTP 503): down\n"


def test_plan_failure_text_is_the_plan_checks_own(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hi."])
    scenes = [{"ordinal": i, "title": "T", "body": "Hi."} for i in range(1, 1001)]
    plan_path.write_text(json.dumps({"scenes": scenes}))
    code, err, _ = go(plan_path, out, Fake([]), tmp_path)
    assert code == 1
    assert err.startswith(PREFIX + "FAIL ")
    assert "exceeds the maximum" in err
    assert "plan plan" not in err
    scenes = [{"ordinal": 1, "title": "\ud800", "body": "Hi."}]
    plan_path.write_text(json.dumps({"scenes": scenes}))
    code, err, _ = go(plan_path, out, Fake([]), tmp_path)
    assert code == 1 and err.startswith(PREFIX + "FAIL ") and "title" in err


def test_wav_failure_wording(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hi."])
    (out / "audio" / "001.wav").unlink()
    code, err, _ = go(plan_path, out, Fake([]), tmp_path)
    assert code == 1
    assert err.startswith(PREFIX + "FAIL scene 1: audio/001.wav")


def test_provider_error_wording_with_and_without_status(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hi."])
    code, err, _ = go(plan_path, out, Fake([fail_with(401, "User not found.")]), tmp_path)
    assert (code, err) == (1, f"{PREFIX}FAIL scene 1: provider error (HTTP 401): User not found.\n")
    code, err, _ = go(plan_path, out, Fake([fail_with(None, "timed out")]), tmp_path)
    assert (code, err) == (1, f"{PREFIX}FAIL scene 1: provider request failed: timed out\n")


def test_key_in_provider_text_is_redacted(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hi."])
    fake = Fake([fail_with(401, f"bad key {KEY} given"), fail_with(None, f"echo {KEY}")])
    code, err, _ = go(plan_path, out, fake, tmp_path)
    assert code == 1
    assert "[redacted]" in err and KEY not in err
    code, err, _ = go(plan_path, out, fake, tmp_path)
    assert "[redacted]" in err and KEY not in err


def test_key_with_whitespace_in_dotenv_is_redacted(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hi."])
    dotenv = tmp_path / ".env"
    dotenv.write_text('OPENROUTER_API_KEY="  file-secret-value  "\n')
    for text in ("file-secret-value", "  file-secret-value  "):
        fake = Fake([fail_with(401, f"bad key {text} given")])
        err = io.StringIO()
        code = run_align(plan_path, NoTerminal(), {}, dotenv, out, lambda k, f=fake: f, err)
        assert code == 1
        assert "file-secret-value" not in err.getvalue()
        assert "[redacted]" in err.getvalue()


def test_process_key_with_whitespace_is_redacted_in_both_forms(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hi."])
    env = {"OPENROUTER_API_KEY": "  padded-secret  "}
    for text in ("padded-secret", "  padded-secret  "):
        fake = Fake([fail_with(500, f"saw {text} here")])
        code, err, _ = go(plan_path, out, fake, tmp_path, env=env)
        assert code == 1
        assert "padded-secret" not in err and "[redacted]" in err


def test_key_not_in_stderr_on_success(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hello there."])
    code, err, _ = go(plan_path, out, Fake([body(HELLO)]), tmp_path)
    assert code == 0 and KEY not in err


@pytest.mark.parametrize("kind", ["directory", "bad bytes"])
def test_unreadable_dotenv_gives_a_message_without_content(tmp_path, kind):
    plan_path, out, _ = pack_dir(tmp_path, ["Hi."])
    dotenv = tmp_path / ".env"
    if kind == "directory":
        dotenv.mkdir()
    else:
        dotenv.write_bytes(b"OPENROUTER_API_KEY=hidden-content\xff\xfe\n")
    fake = Fake([body(HELLO)])
    code, err, keys = go(plan_path, out, fake, tmp_path, env={}, dotenv=dotenv)
    assert code == 1
    assert err.startswith(PREFIX + "FAIL ")
    assert "hidden-content" not in err
    if kind == "bad bytes":
        assert err == f"{PREFIX}FAIL could not read .env\n"
    assert fake.received == [] and keys == []


def test_missing_key_wording(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hi."])
    code, err, _ = go(plan_path, out, Fake([]), tmp_path, env={})
    assert (code, err) == (1, f"{PREFIX}FAIL OPENROUTER_API_KEY is not set\n")


def test_existing_file_overwritten_on_success_and_rerun_is_identical(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hello there."])
    target = out / "line_timings.json"
    target.write_bytes(EXISTING)
    code, _, _ = go(plan_path, out, Fake([body(HELLO)]), tmp_path)
    assert code == 0
    first = target.read_bytes()
    assert first != EXISTING
    code, _, _ = go(plan_path, out, Fake([body(HELLO)]), tmp_path)
    assert code == 0 and target.read_bytes() == first


FAILURES = {
    "provider 500": lambda out: Fake([fail_with(500, "")]),
    "malformed": lambda out: Fake([b"{}"]),
}


@pytest.mark.parametrize("name", list(FAILURES))
def test_existing_file_unchanged_when_the_run_fails(tmp_path, name):
    plan_path, out, _ = pack_dir(tmp_path, ["Hello there."])
    target = out / "line_timings.json"
    target.write_bytes(EXISTING)
    code, _, _ = go(plan_path, out, FAILURES[name](out), tmp_path)
    assert code == 1 and target.read_bytes() == EXISTING


@pytest.mark.parametrize("name", ["missing key", "missing wav", "bad plan"])
def test_existing_file_unchanged_when_a_check_fails(tmp_path, name):
    plan_path, out, _ = pack_dir(tmp_path, ["Hello there."])
    target = out / "line_timings.json"
    target.write_bytes(EXISTING)
    extra = {}
    if name == "missing key":
        extra = {"env": {}}
    elif name == "missing wav":
        (out / "audio" / "001.wav").unlink()
    else:
        plan_path.write_text("nope")
    code, _, _ = go(plan_path, out, Fake([body(HELLO)]), tmp_path, **extra)
    assert code == 1 and target.read_bytes() == EXISTING
