"""run_preflight steps 1-4 (stdin, plan, limits, keys): each failure stops before any directory is touched."""

import os

import pytest
from preflight_helper import FakeStdin, plan_bytes, preflight, spy_calls

from scenevoice.synth import (
    ENV_NAMES,
    PreflightResult,
    RecordEntry,
    RecordSettings,
    serialize_record,
)
from scenevoice.synth.regen_notes import missing_entry_note, missing_record_note

LATER = ("resolve_env", "prepare_out_dir")


def assert_failure(result):
    assert isinstance(result, str)
    assert not result.startswith("scenevoice synth")
    assert "dummy-key-value" not in result


def test_terminal_stdin_without_plan_fails_before_any_io(tmp_path, monkeypatch):
    calls = spy_calls(monkeypatch, *LATER)
    stdin = FakeStdin(plan_bytes(), tty=True)
    out = tmp_path / "out"
    result = preflight(tmp_path, out, plan=False, stdin=stdin)
    assert_failure(result)
    assert result == "no PLAN given and stdin is a terminal"
    assert stdin.reads == 0 and calls == [] and not out.exists()


@pytest.mark.parametrize("stdin", [FakeStdin(b"ignored", tty=True), None], ids=["terminal", "none"])
def test_plan_path_never_consults_stdin(tmp_path, monkeypatch, stdin):
    calls = spy_calls(monkeypatch, "resolve_env")
    result = preflight(tmp_path, tmp_path / "out", stdin=stdin)
    assert isinstance(result, PreflightResult)
    assert calls == ["resolve_env"]  # positive control
    assert stdin is None or stdin.reads == 0


def test_non_terminal_stdin_without_plan_is_read(tmp_path, monkeypatch):
    calls = spy_calls(monkeypatch, "resolve_env")
    stdin = FakeStdin(plan_bytes(), tty=False)
    result = preflight(tmp_path, tmp_path / "out", plan=False, stdin=stdin)
    assert isinstance(result, PreflightResult)
    assert stdin.reads == 1 and calls == ["resolve_env"]


@pytest.mark.parametrize(
    "data",
    [b"not json", plan_bytes(2, body="x" * 9000), plan_bytes(1000)],
    ids=["invalid-plan", "over-byte-limit", "1000-scenes"],
)
def test_plan_failures_stop_before_keys_and_directories(tmp_path, monkeypatch, data):
    calls = spy_calls(monkeypatch, *LATER)
    out = tmp_path / "new" / "out"
    assert_failure(preflight(tmp_path, out, data=data))
    assert calls == [] and not out.parent.exists()


def test_missing_keys_name_each_key_never_a_value(tmp_path, monkeypatch):
    calls = spy_calls(monkeypatch, *LATER)
    out = tmp_path / "out"
    result = preflight(tmp_path, out, env={"GOOGLE_CLOUD_LOCATION": "secret-location-value"})
    assert_failure(result)
    assert result.startswith("Missing:")
    assert all(name in result for name in ENV_NAMES if name != "GOOGLE_CLOUD_LOCATION")
    assert "secret-location-value" not in result
    assert calls == ["resolve_env"] and not out.exists()


def test_missing_key_is_a_missing_key_failure_and_other_refusals_stay_plain(tmp_path):
    result = preflight(tmp_path, tmp_path / "out", env={"GOOGLE_CLOUD_LOCATION": "x"})
    assert result.startswith("Missing:")
    assert result.kind == "missing_key"
    plain = preflight(tmp_path, tmp_path / "out", data=b"not json")
    assert type(plain) is str


MODEL = "gemini-3.8-flash-tts"


SETTINGS = RecordSettings("Callirrhoe", MODEL, "en-GB", None)


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


def run(tmp_path, out, notes=None, settings=SETTINGS, **kw):
    if notes is not None:
        kw["note"] = notes.append
    if settings is not None:
        kw["settings"] = settings
    return preflight(tmp_path, out, scene=2, **kw)


def test_matching_entry_passes_silently_and_carries_every_entry(tmp_path, monkeypatch):
    out = make_out(tmp_path, [entry(1), entry(2), entry(3)])
    notes, calls = [], spy_calls(monkeypatch, "load_record", "settings_mismatch", "probe_out_dir")
    result = run(tmp_path, out, notes)
    assert isinstance(result, PreflightResult) and notes == []
    assert [e.ordinal for e in result.entries] == [1, 2, 3]
    assert calls == ["load_record", "settings_mismatch", "probe_out_dir"]


@pytest.mark.parametrize(
    "entries, note_text, carried",
    [
        (None, missing_record_note(2), []),
        ([entry(1), entry(3)], missing_entry_note(2), [1, 3]),
    ],
    ids=["no-record", "no-entry-for-scene"],
)
def test_missing_settings_note_once_and_pass(tmp_path, entries, note_text, carried):
    out = make_out(tmp_path, entries)
    notes = []
    result = run(tmp_path, out, notes)
    assert isinstance(result, PreflightResult)
    assert notes == [note_text]
    assert [e.ordinal for e in result.entries] == carried


@pytest.mark.parametrize(
    "setup, expected",
    [
        (dict(raw=b"not json"), "not a valid synth record"),
        (dict(entries=[entry(1), entry(2, voice="Charon"), entry(3)]), "settings differ from synth_record.json"),
    ],
    ids=["malformed", "mismatch"],
)
def test_refused_record_never_reaches_the_probe(tmp_path, monkeypatch, setup, expected):
    out = make_out(tmp_path, **setup)
    probes = spy_calls(monkeypatch, "probe_out_dir")
    result = run(tmp_path, out)
    assert isinstance(result, str) and expected in result
    assert probes == []


def test_mismatch_names_recorded_and_passed_values(tmp_path):
    out = make_out(tmp_path, [entry(2, voice="Charon")])
    result = run(tmp_path, out)
    assert 'voice recorded "Charon", passed "Callirrhoe"' in result


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores modes")
def test_scene_range_and_keys_come_before_any_record_read(tmp_path):
    out = make_out(tmp_path, raw=b"not json")
    (out / "synth_record.json").chmod(0)
    try:
        assert "out of range" in preflight(tmp_path, out, scene=9, settings=SETTINGS)
        result = preflight(tmp_path, out, scene=2, settings=SETTINGS, env={})
        assert result.startswith("Missing:")
    finally:
        (out / "synth_record.json").chmod(0o644)
