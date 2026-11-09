import hashlib
import io
import json
import os
import sys

import pytest
from pack_run_helper import FakeStdin, put_wav, scene, write_plan

from scenevoice.pack import run_pack

_SCENES = [scene(1, "One"), scene(2, "Two")]


def _out(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    put_wav(out, 1)
    put_wav(out, 2)
    return out


def _run(plan, out):
    err = io.StringIO()
    code = run_pack(plan, FakeStdin(b""), out, err, "resolve")
    return code, err.getvalue()


def _reference(tmp_path):
    ref = tmp_path / "ref"
    ref.mkdir()
    put_wav(ref, 1)
    put_wav(ref, 2)
    assert _run(write_plan(tmp_path, _SCENES), ref)[0] == 0
    return (ref / "resolve_timeline.otio").read_bytes()


@pytest.mark.parametrize("kind", ["valid", "stale", "malformed", "dir", "dangling"])
def test_leftover_line_timings_is_read_in_an_editor_run(tmp_path, kind):
    expected = _reference(tmp_path)
    out = _out(tmp_path)
    target = out / "line_timings.json"
    if kind == "valid":
        entries = [
            {"ordinal": n, "sha256": hashlib.sha256((out / "audio" / f"{n:03d}.wav").read_bytes()).hexdigest(), "lines": []}
            for n in (1, 2)
        ]
        target.write_text(json.dumps({"scenes": entries}))
    elif kind == "stale":
        entries = [{"ordinal": 1, "sha256": "0" * 64, "lines": []}]
        target.write_text(json.dumps({"scenes": entries}))
    elif kind == "malformed":
        target.write_text("{not json")
    elif kind == "dir":
        target.mkdir()
    else:
        os.symlink(out / "gone", target)
    code, text = _run(write_plan(tmp_path, _SCENES), out)
    if kind in ("malformed", "dir", "dangling"):
        assert code == 1 and "line_timings.json" in text and text.count("\n") == 1
        assert not (out / "resolve_timeline.otio").exists()
        return
    assert code == 0
    assert (out / "resolve_timeline.otio").read_bytes() == expected
    if kind == "valid":
        assert text.count("\n") == 1 and "NOTE" not in text
    else:
        assert "NOTE scene 1: line timings stale" in text and "NOTE scene 2: no line timings entry" in text


def test_timeline_rename_failure_removes_everything(tmp_path, monkeypatch):
    out = _out(tmp_path)
    module = sys.modules["scenevoice.pack.write_pack_files"]
    real = module.os.replace
    calls = []

    def fake(src, dst, *a, **kw):
        calls.append(dst)
        if str(dst).endswith("resolve_timeline.otio"):
            raise OSError("injected")
        return real(src, dst, *a, **kw)

    monkeypatch.setattr(module.os, "replace", fake)
    code, text = _run(write_plan(tmp_path, _SCENES), out)
    assert len(calls) == 2, "positive control: both renames attempted"
    assert code == 1
    assert "scenevoice pack: FAIL " in text and "resolve_timeline.otio" in text
    lines = text.splitlines()
    assert lines[0] == "scenevoice pack: NOTE no line_timings.json, scene markers only"
    assert lines[1].startswith("scenevoice pack: FAIL ") and len(lines) == 2
    assert sorted(os.listdir(out)) == ["audio"]
