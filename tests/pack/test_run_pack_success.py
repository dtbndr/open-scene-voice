"""Plain (no editor) pack runs: success wiring and one failure per check family.

The per-check messages are pinned at the check units in tests/pack and tests/synth; here each
check is only proved to be wired in: exit 1, one FAIL line, nothing written.
"""

import inspect
import io
import os

import pytest
from pack_run_helper import FakeStdin, make_out, plan_bytes, run_text, scene, write_plan

from scenevoice.pack import run_pack

MANIFEST = "scene_manifest.csv"
EXPECTED = (
    b"scene,label,file,duration_s\n"
    b"1,One,audio/001.wav,1.000\n"
    b'2,"Two, too",audio/002.wav,2.000\n'
)
TWO_TOO = [scene(1, "One"), scene(2, "Two, too")]


def test_two_scene_run_from_plan_path_writes_only_the_manifest(tmp_path, capsys):
    out = make_out(tmp_path, frames=(24000, 48000))
    code, text = run_text(write_plan(tmp_path, TWO_TOO), out)
    assert code == 0
    assert (out / MANIFEST).read_bytes() == EXPECTED
    assert text == f"scenevoice pack: OK 2 scenes written to {out}/{MANIFEST}\n"
    assert sorted(p.name for p in out.iterdir()) == ["audio", MANIFEST]
    assert sorted(p.name for p in (out / "audio").iterdir()) == ["001.wav", "002.wav"]
    assert capsys.readouterr().out == ""


def test_two_scene_run_from_stdin_buffer(tmp_path):
    out = make_out(tmp_path, frames=(24000, 48000))
    err = io.StringIO()
    assert run_pack(None, FakeStdin(plan_bytes(TWO_TOO)), out, err) == 0
    assert (out / MANIFEST).read_bytes() == EXPECTED
    assert err.getvalue().startswith("scenevoice pack: OK 2 scenes written to ")


def test_runner_has_plan_stdin_directory_stderr_then_optional_editor():
    parameters = inspect.signature(run_pack).parameters
    assert list(parameters) == ["plan_path", "stdin", "directory", "stderr", "editor", "progress_mode"]
    assert parameters["editor"].default is None
    assert parameters["progress_mode"].default == "text"


def _bad_plan(tmp_path, out):
    plan = tmp_path / "plan.json"
    plan.write_bytes(b"not json")
    return plan, out


def _missing_dir(tmp_path, out):
    return write_plan(tmp_path), tmp_path / "nope"


def _missing_audio_dir(tmp_path, out):
    (out / "audio" / "001.wav").unlink()
    (out / "audio" / "002.wav").unlink()
    (out / "audio").rmdir()
    return write_plan(tmp_path), out


def _missing_wav(tmp_path, out):
    (out / "audio" / "002.wav").unlink()
    return write_plan(tmp_path), out


def _invalid_wav(tmp_path, out):
    (out / "audio" / "001.wav").write_bytes(b"this is not a wav file")
    return write_plan(tmp_path), out


@pytest.mark.parametrize(
    ("setup", "needle"),
    [
        (_bad_plan, None),
        (_missing_dir, "nope"),
        (_missing_audio_dir, "/audio"),
        (_missing_wav, "audio/002.wav"),
        (_invalid_wav, "audio/001.wav"),
    ],
)
def test_each_check_is_wired_in_and_fails_with_one_line_and_no_manifest(tmp_path, setup, needle):
    out = make_out(tmp_path)
    plan, directory = setup(tmp_path, out)
    code, text = run_text(plan, directory)
    assert code == 1
    assert text.startswith("scenevoice pack: FAIL ") and text.count("\n") == 1
    assert needle is None or needle in text
    assert not (out / MANIFEST).exists()


@pytest.mark.parametrize("kind", ["file", "directory"])
def test_existing_manifest_path_is_refused_and_left_untouched(tmp_path, kind):
    out = make_out(tmp_path)
    target = out / MANIFEST
    if kind == "file":
        target.write_bytes(b"old\n")
        os.utime(target, (1_000_000_000, 1_000_000_000))
    else:
        target.mkdir()
    before = target.stat().st_mtime_ns
    code, text = run_text(write_plan(tmp_path), out)
    assert code == 1 and MANIFEST in text
    assert target.stat().st_mtime_ns == before
    assert kind == "directory" or target.read_bytes() == b"old\n"


def test_rename_failure_after_checks_leaves_nothing(tmp_path, monkeypatch):
    out = make_out(tmp_path)
    before = sorted(os.listdir(out))
    calls = []

    def fail(src, dst, *a, **k):
        calls.append(dst)
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "replace", fail)
    code, text = run_text(write_plan(tmp_path), out)
    assert len(calls) == 1, "the checks all passed and the rename was attempted"
    assert code == 1 and text.startswith("scenevoice pack: FAIL ") and text.count("\n") == 1
    assert sorted(os.listdir(out)) == before
