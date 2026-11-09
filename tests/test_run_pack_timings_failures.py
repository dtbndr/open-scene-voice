import os
import sys

import pytest
from pack_timings_helper import make_out, ok_line, run, snapshot, timings_doc, wav_hash


def _plant(out, kind):
    target = out / "line_timings.json"
    if kind == "malformed":
        target.write_text("{not json")
    elif kind == "dir":
        target.mkdir()
    elif kind == "symlink":
        (out / "real.json").write_bytes(b'{"scenes": []}')
        os.symlink(out / "real.json", target)
    elif kind == "dangling":
        os.symlink(out / "gone", target)
    else:
        target.write_text('{"scenes": []}')
        os.chmod(target, 0)
    return target


@pytest.mark.parametrize("kind", ["malformed", "dir", "symlink", "dangling", "unreadable"])
def test_bad_timings_file_fails_naming_it_and_writes_nothing(tmp_path, kind):
    out = make_out(tmp_path)
    target = _plant(out, kind)
    if kind == "unreadable" and os.access(target, os.R_OK):
        pytest.skip("file stays readable (running as root)")
    before = snapshot(out)
    code, text = run(tmp_path, out)
    assert code == 1
    assert text.startswith("scenevoice pack: FAIL ") and "line_timings.json" in text
    assert text.count("\n") == 1, "no NOTE precedes a timings failure"
    assert snapshot(out) == before
    if kind == "unreadable":
        os.chmod(target, 0o600)


@pytest.mark.parametrize("kind", ["malformed", "dir", "symlink", "dangling"])
def test_plain_run_never_reads_the_file(tmp_path, kind, monkeypatch):
    out = make_out(tmp_path)
    reference = make_out(tmp_path, "ref")
    module = sys.modules["scenevoice.pack.run_pack"]
    reader = sys.modules["scenevoice.pack.check_line_timings"]

    def boom(*args):
        raise AssertionError("plain run read the timings file")

    assert run(tmp_path, reference, None)[0] == 0
    _plant(out, kind)
    monkeypatch.setattr(module, "check_line_timings", boom)
    monkeypatch.setattr(reader, "read_line_timings_file", boom)
    code, text = run(tmp_path, out, None)
    assert code == 0
    assert text == f"scenevoice pack: OK 2 scenes written to {out}/scene_manifest.csv\n"
    assert (out / "scene_manifest.csv").read_bytes() == (reference / "scene_manifest.csv").read_bytes()
    assert not (out / "resolve_timeline.otio").exists()


def test_check_4_wav_failure_wins_over_malformed_timings(tmp_path):
    out = make_out(tmp_path)
    (out / "audio" / "002.wav").unlink()
    (out / "line_timings.json").write_text("{not json")
    code, text = run(tmp_path, out)
    assert code == 1
    assert "scene 2" in text and "002.wav" in text and "line_timings.json" not in text


def test_check_3a_timeline_collision_wins_over_malformed_timings(tmp_path):
    out = make_out(tmp_path)
    (out / "resolve_timeline.otio").write_bytes(b"old")
    (out / "line_timings.json").write_text("{not json")
    code, text = run(tmp_path, out)
    assert code == 1
    assert "resolve_timeline.otio" in text and "line_timings.json" not in text


def test_timings_failure_comes_before_check_5(tmp_path, monkeypatch):
    out = make_out(tmp_path)
    (out / "line_timings.json").write_text("{not json")
    module = sys.modules["scenevoice.pack.run_pack"]
    calls = []
    real = module.write_pack_files
    monkeypatch.setattr(module, "write_pack_files", lambda *a: calls.append(a) or real(*a))
    code, _ = run(tmp_path, out)
    assert code == 1 and calls == []
    (out / "line_timings.json").write_bytes(timings_doc([(1, wav_hash(out, 1))]))
    code, text = run(tmp_path, out)
    assert calls, "positive control: a valid file reaches the write step"
    assert code == 0 and text.endswith(ok_line(out))
