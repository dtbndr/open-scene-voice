import io
import os

import pytest
from pack_run_helper import FakeStdin, put_wav, scene, write_plan

from scenevoice.pack import run_pack

_SCENES = [scene(1, "One"), scene(2, "Two")]


def _out(tmp_path, wavs=(1, 2)):
    out = tmp_path / "out"
    out.mkdir()
    for n in wavs:
        put_wav(out, n)
    return out


def _run(plan, out):
    err = io.StringIO()
    code = run_pack(plan, FakeStdin(b""), out, err)
    return code, err.getvalue()


def _assert_failed(code, text, out):
    assert code == 1
    assert text.startswith("scenevoice pack: FAIL ")
    assert text.count("\n") == 1
    assert not (out / "scene_manifest.csv").exists()
    assert not (out / "scene_manifest.csv").is_symlink()


def test_bad_plan(tmp_path):
    out = _out(tmp_path)
    plan = tmp_path / "plan.json"
    plan.write_bytes(b"not json")
    _assert_failed(*_run(plan, out), out)


def test_1000_scenes(tmp_path):
    out = _out(tmp_path)
    plan = write_plan(tmp_path, [scene(i) for i in range(1, 1001)])
    _assert_failed(*_run(plan, out), out)


def test_surrogate_title(tmp_path):
    out = _out(tmp_path)
    plan = write_plan(tmp_path, [scene(1, "a\ud800b"), scene(2)])
    _assert_failed(*_run(plan, out), out)


def test_nonexistent_dir(tmp_path):
    code, text = _run(write_plan(tmp_path, _SCENES), tmp_path / "nope")
    assert code == 1 and text.startswith("scenevoice pack: FAIL ")


def test_dir_is_a_file(tmp_path):
    f = tmp_path / "f"
    f.write_bytes(b"x")
    code, text = _run(write_plan(tmp_path, _SCENES), f)
    assert code == 1 and text.startswith("scenevoice pack: FAIL ")


def test_collision_with_file_keeps_bytes_and_mtime(tmp_path):
    out = _out(tmp_path)
    target = out / "scene_manifest.csv"
    target.write_bytes(b"old\n")
    os.utime(target, (1_000_000_000, 1_000_000_000))
    before = target.stat()
    code, text = _run(write_plan(tmp_path, _SCENES), out)
    assert code == 1
    assert text.startswith("scenevoice pack: FAIL ") and "scene_manifest.csv" in text
    assert target.read_bytes() == b"old\n"
    assert target.stat().st_mtime_ns == before.st_mtime_ns


def test_collision_with_directory(tmp_path):
    out = _out(tmp_path)
    (out / "scene_manifest.csv").mkdir()
    code, text = _run(write_plan(tmp_path, _SCENES), out)
    assert code == 1 and "scene_manifest.csv" in text


def test_collision_with_dangling_symlink(tmp_path):
    out = _out(tmp_path)
    link = out / "scene_manifest.csv"
    try:
        link.symlink_to(tmp_path / "missing-target")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported")
    code, text = _run(write_plan(tmp_path, _SCENES), out)
    assert code == 1 and "scene_manifest.csv" in text
    assert not (tmp_path / "missing-target").exists()


def test_missing_wav_names_scene_and_file(tmp_path):
    out = _out(tmp_path, wavs=(1,))
    code, text = _run(write_plan(tmp_path, _SCENES), out)
    _assert_failed(code, text, out)
    assert "scene 2" in text and "audio/002.wav" in text


def test_invalid_wav(tmp_path):
    out = _out(tmp_path)
    (out / "audio" / "001.wav").write_bytes(b"this is not a wav file")
    code, text = _run(write_plan(tmp_path, _SCENES), out)
    _assert_failed(code, text, out)
    assert "audio/001.wav" in text


def _install_replace(monkeypatch, fail):
    calls = []
    real = os.replace

    def fake(src, dst, *a, **k):
        calls.append(dst)
        if fail:
            raise OSError(28, "No space left on device")
        return real(src, dst, *a, **k)

    monkeypatch.setattr(os, "replace", fake)
    return calls


def test_replace_positive_control(tmp_path, monkeypatch):
    out = _out(tmp_path)
    calls = _install_replace(monkeypatch, fail=False)
    code, _ = _run(write_plan(tmp_path, _SCENES), out)
    assert code == 0 and len(calls) == 1
    assert (out / "scene_manifest.csv").exists()


def test_rename_failure_after_checks_leaves_nothing(tmp_path, monkeypatch):
    out = _out(tmp_path)
    before = sorted(os.listdir(out))
    calls = _install_replace(monkeypatch, fail=True)
    code, text = _run(write_plan(tmp_path, _SCENES), out)
    assert len(calls) == 1
    _assert_failed(code, text, out)
    assert sorted(os.listdir(out)) == before
    assert not list(out.glob("*.csv"))
