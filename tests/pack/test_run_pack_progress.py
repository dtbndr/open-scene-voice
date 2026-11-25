"""run_pack --progress json: note, ok and fail events with kinds; no scene events (text unchanged)."""

import io
import json
import sys

import pytest
from pack_run_helper import FakeStdin, make_out, run_text, write_plan

from scenevoice.pack import run_pack


@pytest.fixture(autouse=True)
def _offline_clean_env(clean_env, no_sockets):
    """Every test here runs run_pack on real files: empty cwd, no sockets."""


def run_json(plan, out, editor=None, stdin=None):
    err = io.StringIO()
    code = run_pack(plan, stdin or FakeStdin(b""), out, err, editor, progress_mode="json")
    return code, [json.loads(line) for line in err.getvalue().splitlines()]


def only_fail(events, kind):
    assert [e["event"] for e in events] == ["fail"]
    assert events[0]["command"] == "pack" and events[0]["kind"] == kind
    assert not events[0]["message"].startswith("scenevoice pack:")
    return events[0]


def test_success_is_one_ok_event_with_the_written_text(tmp_path):
    out = make_out(tmp_path)
    code, events = run_json(write_plan(tmp_path), out)
    assert code == 0
    assert [e["event"] for e in events] == ["ok"]
    assert events[0]["message"] == f"2 scenes written to {out}/scene_manifest.csv"


def test_editor_notes_are_note_events_in_text_order_then_one_ok(tmp_path):
    out = make_out(tmp_path)
    plan = write_plan(tmp_path)
    _, text = run_text(plan, out, "resolve")
    (out / "scene_manifest.csv").unlink()
    (out / "resolve_timeline.otio").unlink()
    code, events = run_json(plan, out, "resolve")
    assert code == 0
    assert [e["event"] for e in events] == ["note", "ok"]
    lines = text.splitlines()
    assert [e["message"] for e in events] == [
        line.removeprefix("scenevoice pack: NOTE ").removeprefix("scenevoice pack: OK ")
        for line in lines
    ]
    assert events[0]["message"] == "no line_timings.json, scene markers only"
    assert events[1]["message"].endswith("resolve_timeline.otio")


def test_text_mode_is_unchanged_by_the_parameter(tmp_path):
    out = make_out(tmp_path)
    err = io.StringIO()
    code = run_pack(write_plan(tmp_path), FakeStdin(b""), out, err, None, progress_mode="text")
    assert code == 0
    assert err.getvalue() == f"scenevoice pack: OK 2 scenes written to {out}/scene_manifest.csv\n"


def test_plan_problem_is_invalid_input(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_bytes(b"not json")
    code, events = run_json(plan, make_out(tmp_path))
    assert code == 1
    only_fail(events, "invalid_input")


def test_terminal_stdin_is_invalid_input(tmp_path):
    code, events = run_json(None, make_out(tmp_path), stdin=FakeStdin(b"", tty=True))
    assert code == 1
    assert only_fail(events, "invalid_input")["message"] == "no PLAN given and stdin is a terminal"


def test_missing_dir_is_invalid_input(tmp_path):
    code, events = run_json(write_plan(tmp_path), tmp_path / "missing")
    assert code == 1
    only_fail(events, "invalid_input")


def test_missing_audio_dir_is_invalid_input(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    code, events = run_json(write_plan(tmp_path), out)
    assert code == 1
    only_fail(events, "invalid_input")


def test_existing_manifest_is_invalid_input(tmp_path):
    out = make_out(tmp_path)
    (out / "scene_manifest.csv").write_bytes(b"old")
    code, events = run_json(write_plan(tmp_path), out)
    assert code == 1
    only_fail(events, "invalid_input")


def test_existing_timeline_is_invalid_input_in_an_editor_run(tmp_path):
    out = make_out(tmp_path)
    (out / "resolve_timeline.otio").write_bytes(b"old")
    code, events = run_json(write_plan(tmp_path), out, "resolve")
    assert code == 1
    only_fail(events, "invalid_input")


def test_missing_wav_is_invalid_input(tmp_path):
    out = make_out(tmp_path, frames=(24000,))
    code, events = run_json(write_plan(tmp_path), out)
    assert code == 1
    only_fail(events, "invalid_input")


def test_bad_line_timings_file_is_invalid_input(tmp_path):
    out = make_out(tmp_path)
    (out / "line_timings.json").write_bytes(b"not json")
    code, events = run_json(write_plan(tmp_path), out, "resolve")
    assert code == 1
    only_fail(events, "invalid_input")


def test_manifest_write_failure_is_other(tmp_path, monkeypatch):
    def boom(directory, data):
        raise OSError("injected")

    monkeypatch.setattr(sys.modules["scenevoice.pack.write_manifest"], "write_temp_file", boom)
    code, events = run_json(write_plan(tmp_path), make_out(tmp_path))
    assert code == 1
    assert only_fail(events, "other")["message"] == "could not write scene_manifest.csv"


def test_timeline_write_failure_is_other_after_its_notes(tmp_path, monkeypatch):
    def boom(directory, data):
        raise OSError("injected")

    monkeypatch.setattr(sys.modules["scenevoice.pack.write_pack_files"], "write_temp_file", boom)
    code, events = run_json(write_plan(tmp_path), make_out(tmp_path), "resolve")
    assert code == 1
    assert [e["event"] for e in events] == ["note", "fail"]
    assert events[1]["kind"] == "other"
