import json
import os
import sys

import pytest

from scenevoice.synth import (
    PreflightResult,
    RecordEntry,
    RecordSettings,
    serialize_record,
)
from scenevoice.synth.run_preflight import run_preflight

MODULE = "scenevoice.synth.run_preflight"
ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": "dummy-key-value",
}
MODEL = "gemini-3.8-flash-tts"
SETTINGS = RecordSettings("Callirrhoe", MODEL, "en-GB", None)
MALFORMED = (
    "synth_record.json is not a valid synth record "
    "(delete it to regenerate without a settings check)"
)
SHA = "a" * 64


def entry(n, voice="Callirrhoe"):
    return RecordEntry(n, SHA, voice, MODEL, "en-GB", None, None)


def make_out(tmp_path, entries=None, raw=None):
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    if entries is not None:
        (out / "synth_record.json").write_bytes(serialize_record(entries))
    if raw is not None:
        (out / "synth_record.json").write_bytes(raw)
    return out


def run(tmp_path, out, scene=2, settings=SETTINGS, notes=None, env=ENV):
    plan = tmp_path / "plan.json"
    scenes = [{"ordinal": i, "title": "t", "body": f"b{i}"} for i in (1, 2, 3)]
    plan.write_text(json.dumps({"scenes": scenes}))
    kw = {}
    if settings is not None:
        kw["settings"] = settings
    if notes is not None:
        kw["note"] = notes.append
    return run_preflight(plan, None, env, tmp_path / "absent.env", out, scene=scene, **kw)


def spy_probe(monkeypatch):
    calls = []
    real = sys.modules[MODULE].probe_out_dir
    monkeypatch.setattr(
        sys.modules[MODULE], "probe_out_dir", lambda d: calls.append(d) or real(d)
    )
    return calls


def test_matching_entry_passes_without_note_and_carries_entries(tmp_path, monkeypatch):
    out = make_out(tmp_path, [entry(1), entry(2), entry(3)])
    notes, probes = [], spy_probe(monkeypatch)
    result = run(tmp_path, out, notes=notes)
    assert isinstance(result, PreflightResult)
    assert notes == []
    assert [e.ordinal for e in result.entries] == [1, 2, 3]
    assert len(probes) == 1  # positive control for the probe spy


def test_entries_default_is_empty_tuple():
    assert PreflightResult([], {}).entries == ()


def test_absent_record_notes_once_and_carries_no_entries(tmp_path):
    out = make_out(tmp_path)
    notes = []
    result = run(tmp_path, out, notes=notes)
    assert isinstance(result, PreflightResult) and result.entries == ()
    assert notes == [
        "no settings recorded for scene 2 (synth_record.json is missing); settings not checked"
    ]


def test_record_without_entry_notes_no_entry_text(tmp_path):
    out = make_out(tmp_path, [entry(1), entry(3)])
    notes = []
    result = run(tmp_path, out, notes=notes)
    assert isinstance(result, PreflightResult)
    assert [e.ordinal for e in result.entries] == [1, 3]
    assert notes == [
        "no settings recorded for scene 2 in synth_record.json; settings not checked"
    ]


def test_malformed_record_refused_and_probe_never_runs(tmp_path, monkeypatch):
    out = make_out(tmp_path, raw=b"not json")
    probes = spy_probe(monkeypatch)
    assert run(tmp_path, out) == MALFORMED
    assert probes == []


def test_mismatch_refused_and_probe_never_runs(tmp_path, monkeypatch):
    out = make_out(tmp_path, [entry(1), entry(2, voice="Charon"), entry(3)])
    probes = spy_probe(monkeypatch)
    assert run(tmp_path, out) == (
        'scene 2 settings differ from synth_record.json: voice recorded "Charon", '
        'passed "Callirrhoe"'
    )
    assert probes == []


def test_refused_target_beats_malformed_record(tmp_path):
    out = make_out(tmp_path, raw=b"not json")
    (out / "audio" / "002.wav").mkdir()
    assert run(tmp_path, out) == "002.wav exists and is not a regular file"


def test_non_regular_record_beats_malformed(tmp_path):
    out = make_out(tmp_path)
    (out / "synth_record.json").mkdir()
    assert run(tmp_path, out) == "synth_record.json exists and is not a regular file"


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores modes")
def test_malformed_record_beats_unwritable_audio(tmp_path):
    out = make_out(tmp_path, raw=b"not json")
    (out / "audio").chmod(0o555)
    try:
        assert run(tmp_path, out) == MALFORMED
        # positive control: with a good record the probe does fail here
        (out / "synth_record.json").write_bytes(serialize_record([entry(2)]))
        assert run(tmp_path, out) != MALFORMED
        assert isinstance(run(tmp_path, out), str)
    finally:
        (out / "audio").chmod(0o755)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores modes")
def test_scene_range_and_env_come_before_any_record_read(tmp_path):
    out = make_out(tmp_path, raw=b"not json")
    (out / "synth_record.json").chmod(0)
    try:
        assert run(tmp_path, out, scene=9) == "--scene 9 is out of range (the plan has 3 scenes)"
        assert run(tmp_path, out, env={}).startswith("missing environment variables")
    finally:
        (out / "synth_record.json").chmod(0o644)


def test_settings_none_does_not_read_the_record(tmp_path, monkeypatch):
    out = make_out(tmp_path, raw=b"not json")
    reads = []
    monkeypatch.setattr(sys.modules[MODULE], "load_record", lambda d: reads.append(d))
    result = run(tmp_path, out, settings=None)
    assert isinstance(result, PreflightResult)
    assert reads == []
    # positive control
    run(tmp_path, out)
    assert len(reads) == 1


def test_entry_beyond_plan_does_not_matter(tmp_path):
    out = make_out(tmp_path, [entry(2), entry(7)])
    notes = []
    result = run(tmp_path, out, notes=notes)
    assert isinstance(result, PreflightResult) and notes == []
