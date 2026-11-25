"""run_synth --progress json: scene, note, ok and fail events with kinds (text mode unchanged)."""

import json
import sys

import pytest
import run_synth_helper as full
import synth_scene_helper as scene_helper
from run_synth_helper import KEY, PREFIX, Recorder
from wav_helper import make_wav

from scenevoice.synth import ProviderAudio, ProviderError
from scenevoice.synth.regen_notes import missing_record_note

RECORD_HOOK_MODULE = "scenevoice.synth.make_record_hook"
RUN_MODULE = "scenevoice.synth.run_synth"


@pytest.fixture(autouse=True)
def _offline_clean_env(clean_env):
    """Every test here runs run_synth on real files: empty cwd, no key in env, no sockets."""


def events(err):
    lines = err.splitlines()
    assert lines
    return [json.loads(line) for line in lines]


def run_json(tmp_path, rec, **kw):
    code, err = full.run(tmp_path, rec, progress_mode="json", **kw)
    return code, events(err)


def failing_at(n, error):
    def impl(count):
        if count == n:
            raise error
        return ProviderAudio("audio/wav", make_wav())

    return Recorder(provider=impl)


def test_full_run_writes_started_then_done_per_scene_then_ok(tmp_path):
    code, evs = run_json(tmp_path, Recorder())
    assert code == 0
    scene_events = [e for e in evs if e["event"] == "scene"]
    assert [(e["state"], e["scene"], e["total"]) for e in scene_events] == [
        (state, n, 3) for n in (1, 2, 3) for state in ("started", "done")
    ]
    assert all("path" not in e for e in scene_events if e["state"] == "started")
    assert [e["path"] for e in scene_events if e["state"] == "done"] == [
        f"audio/00{n}.wav" for n in (1, 2, 3)
    ]
    assert [e["event"] for e in evs] == ["scene"] * 6 + ["ok"]
    assert evs[1]["message"] == "scene 1/3 written to audio/001.wav"
    assert evs[-1]["message"].startswith("3 scenes written to ")
    assert {e["command"] for e in evs} == {"synth"}


def test_scene_mode_writes_one_pair_with_total_from_the_plan(tmp_path):
    scene_helper.make_out(tmp_path)
    code, err = scene_helper.run(tmp_path, scene_helper.Rec(), scene=2, progress_mode="json")
    evs = events(err)
    assert code == 0
    assert [e["event"] for e in evs] == ["note", "scene", "scene", "ok"]
    assert evs[0]["message"] == missing_record_note(2)
    assert [(e["state"], e["scene"], e["total"]) for e in evs[1:3]] == [
        ("started", 2, 3),
        ("done", 2, 3),
    ]
    assert evs[2]["path"] == "audio/002.wav" and "path" not in evs[1]


def test_provider_key_never_appears_in_any_json_line(tmp_path):
    rec = failing_at(2, ProviderError(f"denied for {KEY}\nretry", status=403))
    code, err = full.run(tmp_path, rec, progress_mode="json")
    assert code == 1 and len(rec.calls) == 2  # positive control: the error was raised
    assert KEY not in err and "[redacted]" in err
    assert events(err)[-1]["kind"] == "bad_key"


def test_text_mode_is_unchanged(tmp_path):
    code, err = full.run(tmp_path, Recorder())
    assert code == 0
    lines = err.splitlines()
    assert lines[0] == PREFIX + "scene 1/3 written to audio/001.wav"
    assert len(lines) == 4 and lines[3].startswith(PREFIX + "OK 3 scenes")


def _fail_event(tmp_path, rec, **kw):
    code, evs = run_json(tmp_path, rec, **kw)
    assert code == 1
    return evs[-1]


def _early_refusal(tmp_path):
    return _fail_event(tmp_path, Recorder(), plan=_bad_plan(tmp_path))


def _bad_plan(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not json")
    return path


def _missing_key(tmp_path):
    return _fail_event(tmp_path, Recorder(), env={})


def _record_write_after_call(tmp_path, monkeypatch):
    fake_calls = []

    def fake(directory, data):
        fake_calls.append(data)
        return "could not write synth_record.json"

    monkeypatch.setattr(sys.modules[RECORD_HOOK_MODULE], "write_record_file", fake)
    event = _fail_event(tmp_path, Recorder())
    assert len(fake_calls) == 1  # positive control
    return event


@pytest.mark.parametrize(
    ("case", "kind", "scene"),
    [
        ("early_refusal", "invalid_input", None),
        ("missing_key", "missing_key", None),
        ("record_write_after_call", "other", 1),
    ],
)
def test_failure_kind_follows_the_phase_rule(tmp_path, monkeypatch, case, kind, scene):
    if case == "record_write_after_call":
        event = _record_write_after_call(tmp_path, monkeypatch)
    else:
        event = {
            "early_refusal": _early_refusal,
            "missing_key": _missing_key,
        }[case](tmp_path)
    assert event["event"] == "fail"
    assert (event["kind"], event["scene"], event["line"], event["status"]) == (kind, scene, None, None)


def test_http_status_failure_carries_kind_status_and_scene(tmp_path):
    rec = failing_at(2, ProviderError("quota exceeded", status=429))
    event = _fail_event(tmp_path, rec)
    assert (event["kind"], event["status"], event["scene"]) == ("quota", 429, 2)
    assert event["message"] == "scene 2: quota exceeded"


def test_transport_failure_is_provider_down_without_status(tmp_path):
    rec = failing_at(2, ProviderError("connection reset", transport=True))
    event = _fail_event(tmp_path, rec)
    assert (event["kind"], event["status"], event["scene"]) == ("provider_down", None, 2)
