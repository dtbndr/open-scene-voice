"""run_align --progress json: scene, note, ok and fail events with kinds (text mode unchanged)."""

import io
import json
import sys

import pytest
from align_run_helper import (
    BODIES,
    ENV,
    HELLO,
    KEY,
    PREFIX,
    Fake,
    NoTerminal,
    alignment_at,
    body,
    fail_if_called,
    fail_with,
    pack_dir,
    worked_record,
)
from record_helper import eleven_entry, write_record

from scenevoice.align.run_align import run_align

RUN_MODULE = "scenevoice.align.run_align"
TEXTS3 = ["Hello there.", "Hello there.", "Hello there."]


@pytest.fixture(autouse=True)
def _offline_clean_env(clean_env):
    """Every test here runs run_align on real files: empty cwd, no key in env, no sockets."""


def run(tmp_path, plan_path, out, factory, env=ENV, mode="json", plan_stdin=None):
    err = io.StringIO()
    code = run_align(
        plan_path,
        plan_stdin or NoTerminal(),
        env,
        tmp_path / "no.env",
        out,
        factory,
        err,
        progress_mode=mode,
    )
    return code, err.getvalue()


def run_json(tmp_path, plan_path, out, fake, env=ENV):
    code, err = run(tmp_path, plan_path, out, lambda key: fake, env=env)
    lines = err.splitlines()
    assert lines
    return code, [json.loads(line) for line in lines]


def test_full_run_writes_started_then_done_per_scene_then_ok(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, TEXTS3)
    code, evs = run_json(tmp_path, plan_path, out, Fake([body(HELLO)] * 3))
    assert code == 0
    scene_events = [e for e in evs if e["event"] == "scene"]
    assert [(e["state"], e["scene"], e["total"]) for e in scene_events] == [
        (state, n, 3) for n in (1, 2, 3) for state in ("started", "done")
    ]
    assert all("path" not in e for e in scene_events)
    assert [e["message"] for e in scene_events] == [
        m for n in (1, 2, 3) for m in (f"scene {n}/3 transcribing", f"scene {n}/3 aligned")
    ]
    assert [e["event"] for e in evs] == ["scene"] * 6 + ["note", "ok"]
    assert {e["command"] for e in evs} == {"align"}


def test_record_routed_scene_is_done_without_started(tmp_path):
    texts = ["Hello. ...", "Hello there. Mango."]
    plan_path, out, wavs = pack_dir(tmp_path, texts)
    write_record(
        out,
        eleven_entry(1, wavs[0], texts[0], alignment=alignment_at(texts[0], {0: 0.2})),
        eleven_entry(2, wavs[1], "other text"),
    )
    code, evs = run_json(tmp_path, plan_path, out, Fake([body(HELLO)]))
    assert code == 0
    scene_events = [e for e in evs if e["event"] == "scene"]
    assert [(e["state"], e["scene"], e["total"], e["message"]) for e in scene_events] == [
        ("done", 1, 2, "scene 1/2 from synth record"),
        ("started", 2, 2, "scene 2/2 transcribing"),
        ("done", 2, 2, "scene 2/2 aligned"),
    ]
    assert all("path" not in e for e in scene_events)
    notes = [e["message"] for e in evs if e["event"] == "note"]
    assert notes == [
        "scene 1 line 2: no match, start_ms null",
        "scene 2: alignment text differs from plan body, transcribed",
        "scene 2 line 2: no match, start_ms null",
    ]
    assert evs[-1]["event"] == "ok"


def test_all_record_run_has_done_events_only_and_never_calls_the_factory(tmp_path):
    plan_path, out, wavs = pack_dir(tmp_path, BODIES)
    worked_record(out, wavs)
    code, err = run(tmp_path, plan_path, out, fail_if_called)
    evs = [json.loads(line) for line in err.splitlines()]
    assert code == 0
    assert [(e["event"], e.get("state")) for e in evs] == [("scene", "done")] * 2 + [("ok", None)]
    assert [e["message"] for e in evs[:2]] == [
        "scene 1/2 from synth record",
        "scene 2/2 from synth record",
    ]


def test_missing_key_is_missing_key_with_no_scene_events(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, TEXTS3)
    fake = Fake([body(HELLO)] * 3)
    code, evs = run_json(tmp_path, plan_path, out, fake, env={})
    assert code == 1 and fake.received == []
    assert [e["event"] for e in evs] == ["fail"]
    assert evs[-1]["kind"] == "missing_key"
    assert evs[-1]["scene"] is None and evs[-1]["status"] is None


def test_http_status_failure_keeps_kind_scene_and_status(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, TEXTS3)
    fake = Fake([body(HELLO), fail_with(429, "slow down"), body(HELLO)])
    code, evs = run_json(tmp_path, plan_path, out, fake)
    assert code == 1 and len(fake.received) == 2
    last = evs[-1]
    assert (last["event"], last["kind"], last["scene"], last["status"]) == ("fail", "quota", 2, 429)
    assert last["message"].startswith("scene 2: provider error (HTTP 429)")
    assert [(e["state"], e["scene"]) for e in evs if e["event"] == "scene"] == [
        ("started", 1),
        ("done", 1),
        ("started", 2),
    ]


def test_transport_failure_is_provider_down_with_null_status(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, TEXTS3)
    code, evs = run_json(tmp_path, plan_path, out, Fake([fail_with(None, "timed out")]))
    last = evs[-1]
    assert code == 1
    assert (last["kind"], last["scene"], last["status"]) == ("provider_down", 1, None)


def test_malformed_transcription_body_is_other(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, TEXTS3)
    code, evs = run_json(tmp_path, plan_path, out, Fake([b"not json"]))
    last = evs[-1]
    assert code == 1
    assert (last["kind"], last["scene"], last["status"]) == ("other", 1, None)
    assert last["message"].startswith("scene 1: malformed response")


def test_provider_key_never_appears_in_any_json_line(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, TEXTS3)
    fake = Fake([fail_with(403, f"denied for {KEY}\nretry")])
    code, err = run(tmp_path, plan_path, out, lambda key: fake)
    assert code == 1 and len(fake.received) == 1  # positive control: the error was raised
    assert KEY not in err and "[redacted]" in err
    assert json.loads(err.splitlines()[-1])["kind"] == "bad_key"


def test_plan_problem_is_invalid_input(tmp_path):
    _, out, _ = pack_dir(tmp_path, TEXTS3)
    code, evs = run_json(tmp_path, tmp_path / "missing.json", out, Fake([]))
    assert code == 1
    assert [e["event"] for e in evs] == ["fail"] and evs[0]["kind"] == "invalid_input"


def test_missing_directory_is_invalid_input(tmp_path):
    plan_path, _, _ = pack_dir(tmp_path, TEXTS3)
    code, evs = run_json(tmp_path, plan_path, tmp_path / "nowhere", Fake([]))
    assert code == 1
    assert [e["event"] for e in evs] == ["fail"] and evs[0]["kind"] == "invalid_input"


def test_missing_wav_is_invalid_input(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, TEXTS3, make_wavs=False)
    code, evs = run_json(tmp_path, plan_path, out, Fake([]))
    assert code == 1
    assert [e["event"] for e in evs] == ["fail"] and evs[0]["kind"] == "invalid_input"


def test_record_problem_is_invalid_input(tmp_path):
    plan_path, out, wavs = pack_dir(tmp_path, BODIES)
    worked_record(out, wavs[:1] + [wavs[0]])  # scene 2 sha256 differs from its WAV
    code, evs = run_json(tmp_path, plan_path, out, Fake([]))
    assert code == 1
    assert [e["event"] for e in evs] == ["fail"]
    assert evs[0]["kind"] == "invalid_input" and "re-run synth --scene 2" in evs[0]["message"]


def test_timings_write_failure_after_calls_is_other(tmp_path, monkeypatch):
    plan_path, out, _ = pack_dir(tmp_path, TEXTS3)
    monkeypatch.setattr(sys.modules[RUN_MODULE], "write_timings_file", lambda d, data: "disk full")
    fake = Fake([body(HELLO)] * 3)
    code, evs = run_json(tmp_path, plan_path, out, fake)
    assert code == 1 and len(fake.received) == 3  # positive control: the stub was reached
    assert (evs[-1]["event"], evs[-1]["kind"], evs[-1]["scene"]) == ("fail", "other", None)
    assert evs[-1]["message"] == "disk full"


def test_text_mode_is_unchanged(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, TEXTS3)
    code, err = run(tmp_path, plan_path, out, lambda key: Fake([body(HELLO)] * 3), mode="text")
    assert code == 0
    lines = err.splitlines()
    assert lines[0] == PREFIX + "NOTE no synth_record.json, all scenes transcribed"
    assert len(lines) == 2 and lines[1].startswith(PREFIX + "OK 3 scenes")


def test_started_is_written_before_each_transcription_call(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, TEXTS3)
    err = io.StringIO()
    seen = []

    def transcriber(wav):
        last = json.loads(err.getvalue().splitlines()[-1])
        seen.append((last["event"], last["state"], last["scene"]))
        return body(HELLO)

    code = run_align(
        plan_path, NoTerminal(), ENV, tmp_path / "no.env", out, lambda key: transcriber, err,
        progress_mode="json",
    )
    assert code == 0
    assert seen == [("scene", "started", n) for n in (1, 2, 3)]
