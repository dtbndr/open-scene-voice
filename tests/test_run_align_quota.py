import json

import pytest
from align_run_helper import HELLO, Fake, NoTerminal, body, fail_with, go, pack_dir
from record_helper import RECORD_FILE, eleven_entry, per_char_alignment, write_record
from wav_helper import make_wav

TEXTS3 = ["Hello there.", "Hello there.", "Hello there."]


def test_empty_body_500_names_scene_and_status(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, TEXTS3)
    fake = Fake([body([(" nope", 0.1)]), fail_with(500, ""), body(HELLO)])
    code, err, _ = go(plan_path, out, fake, tmp_path)
    assert code == 1
    assert len(fake.received) == 2
    assert err.startswith("scenevoice align: FAIL scene 2:")
    assert "HTTP 500" in err
    assert "NOTE" not in err
    assert err.count("\n") == 1
    assert not (out / "line_timings.json").exists()


def test_no_byte_limit_on_scene_body(tmp_path):
    text = "Hello there. " * 700
    assert len(text.encode()) > 8000
    plan_path, out, _ = pack_dir(tmp_path, [text])
    fake = Fake([body(HELLO)])
    code, err, _ = go(plan_path, out, fake, tmp_path)
    assert code == 0
    assert err.rstrip("\n").splitlines()[-1].startswith("scenevoice align: OK 1 scenes, 700 lines")
    assert len(fake.received) == 1
    assert (out / "line_timings.json").exists()


def test_exactly_n_calls_in_plan_order(tmp_path):
    plan_path, out, wavs = pack_dir(tmp_path, TEXTS3)
    fake = Fake([body(HELLO)] * 3)
    code, _, _ = go(plan_path, out, fake, tmp_path)
    assert code == 0
    assert fake.received == wavs
    assert len(set(wavs)) == 3


@pytest.mark.parametrize("failing", [1, 2, 3])
def test_failure_stops_at_first_failing_scene(tmp_path, failing):
    plan_path, out, wavs = pack_dir(tmp_path, TEXTS3)
    items = [body([(" nope", 0.1)])] * 3
    items[failing - 1] = fail_with(429, "slow down")
    fake = Fake(items)
    code, err, _ = go(plan_path, out, fake, tmp_path)
    assert code == 1
    assert fake.received == wavs[:failing]
    assert f"FAIL scene {failing}:" in err
    assert "HTTP 429" in err
    assert "NOTE" not in err
    assert not (out / "line_timings.json").exists()


def test_transport_error_is_not_retried(tmp_path):
    plan_path, out, wavs = pack_dir(tmp_path, TEXTS3)
    fake = Fake([fail_with(None, "timed out")] * 3)
    code, err, _ = go(plan_path, out, fake, tmp_path)
    assert code == 1
    assert len(fake.received) == 1
    assert "FAIL scene 1: provider request failed: timed out" in err


MALFORMED = {
    "not json": b"<html>",
    "bad utf-8": b"\xff\xfe",
    "not an object": b"[1]",
    "no words": b"{}",
    "empty words": b'{"words": []}',
    "entry not object": b'{"words": [1]}',
    "word not string": b'{"words": [{"word": 1, "start": 0}]}',
    "start missing": b'{"words": [{"word": "a"}]}',
    "start string": b'{"words": [{"word": "a", "start": "0"}]}',
    "start bool": b'{"words": [{"word": "a", "start": true}]}',
    "start negative": b'{"words": [{"word": "a", "start": -1}]}',
    "start NaN": b'{"words": [{"word": "a", "start": NaN}]}',
    "start infinite": b'{"words": [{"word": "a", "start": 1e999}]}',
    "start huge integer": b'{"words": [{"word": "a", "start": ' + b"9" * 400 + b"}]}",
    "decreasing": b'{"words": [{"word": "a", "start": 2}, {"word": "b", "start": 1}]}',
    "punctuation only": b'{"words": [{"word": "...", "start": 0}]}',
}


@pytest.mark.parametrize("raw", list(MALFORMED.values()), ids=list(MALFORMED))
def test_malformed_response_stops_without_a_further_call(tmp_path, raw):
    plan_path, out, _ = pack_dir(tmp_path, TEXTS3[:2])
    fake = Fake([raw, body(HELLO)])
    code, err, _ = go(plan_path, out, fake, tmp_path)
    assert code == 1
    assert len(fake.received) == 1
    assert err.startswith("scenevoice align: FAIL scene 1: malformed response: ")
    assert "Traceback" not in err
    assert not (out / "line_timings.json").exists()


class Terminal:
    def isatty(self):
        return True

    def read(self):
        raise AssertionError("stdin must not be read")


def _setup(tmp_path, name):
    """Return (plan_path, out, kwargs for go) for a failure at checks 2 to 6."""
    plan_path, out, _ = pack_dir(tmp_path, TEXTS3[:2])
    extra = {}
    if name == "terminal stdin":
        plan_path, extra = None, {"stdin": Terminal()}
    elif name == "bad plan":
        plan_path.write_text("{not json")
    elif name == "1000 scenes":
        scenes = [{"ordinal": i, "title": "T", "body": "Hi."} for i in range(1, 1001)]
        plan_path.write_text(json.dumps({"scenes": scenes}))
    elif name == "bad title":
        scenes = [{"ordinal": 1, "title": "\ud800", "body": "Hi."}]
        plan_path.write_text(json.dumps({"scenes": scenes}))
    elif name == "missing dir":
        out = tmp_path / "nodir"
    elif name == "missing audio":
        (out / "audio" / "001.wav").unlink()
        (out / "audio" / "002.wav").unlink()
        (out / "audio").rmdir()
    elif name == "timings is a directory":
        (out / "line_timings.json").mkdir()
    elif name == "missing wav":
        (out / "audio" / "002.wav").unlink()
    elif name == "999 frames":
        (out / "audio" / "002.wav").write_bytes(make_wav(999))
    elif name == "missing key":
        extra = {"env": {}}
    elif name == "record is a directory":
        (out / RECORD_FILE).mkdir()
    elif name == "malformed record":
        (out / RECORD_FILE).write_text("{not json", encoding="utf-8")
    else:
        _record_case(out, name)
    return plan_path, out, extra


def _record_case(out, name):
    wavs = [(out / "audio" / f"{n:03d}.wav").read_bytes() for n in (1, 2)]
    first = eleven_entry(1, wavs[0], TEXTS3[0])
    if name == "record missing entry":
        write_record(out, first)
    elif name == "record sha256 mismatch":
        write_record(out, first, eleven_entry(2, wavs[1], TEXTS3[1], sha256="a" * 64))
    else:
        big = per_char_alignment(TEXTS3[1])
        big["character_start_times_seconds"][0] = 1e306
        write_record(out, first, eleven_entry(2, wavs[1], TEXTS3[1], alignment=big))


PRE_CALL = [
    "terminal stdin",
    "bad plan",
    "1000 scenes",
    "bad title",
    "missing dir",
    "missing audio",
    "timings is a directory",
    "missing wav",
    "999 frames",
    "missing key",
    "record is a directory",
    "malformed record",
    "record missing entry",
    "record sha256 mismatch",
    "record overflow",
]

NAMED = {
    "record is a directory": ["synth_record.json"],
    "malformed record": ["synth_record.json"],
    "record missing entry": ["synth_record.json", "scene 2"],
    "record sha256 mismatch": ["synth_record.json", "scene 2"],
    "record overflow": ["synth_record.json", "scene 2"],
}


@pytest.mark.parametrize("name", PRE_CALL)
def test_zero_calls_for_every_failure_before_the_calls(tmp_path, name):
    plan_path, out, extra = _setup(tmp_path, name)
    fake = Fake([body(HELLO)] * 2)
    code, err, keys = go(plan_path, out, fake, tmp_path, **extra)
    assert code == 1
    assert err.startswith("scenevoice align: FAIL ")
    assert err.count("\n") == 1
    for needle in NAMED.get(name, []):
        assert needle in err
    assert fake.received == []
    assert keys == []
    assert not (out / "line_timings.json").is_file()


def test_positive_control_the_unbroken_setup_makes_calls(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, TEXTS3[:2])
    fake = Fake([body(HELLO)] * 2)
    code, _, keys = go(plan_path, out, fake, tmp_path, stdin=NoTerminal())
    assert code == 0 and len(fake.received) == 2 and keys == ["dummy-key-value"]
