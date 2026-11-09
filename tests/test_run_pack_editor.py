import io
import os
import stat

from pack_run_helper import FakeStdin, put_wav, scene, write_plan

from scenevoice.pack import build_timeline, run_pack
from scenevoice.synth import PlanScene

_SCENES = [scene(1, "One"), scene(2, "Two")]
_NOTE = "scenevoice pack: NOTE no line_timings.json, scene markers only\n"
_OK = "scenevoice pack: OK 2 scenes written to {d}/scene_manifest.csv and {d}/resolve_timeline.otio\n"


def _out(tmp_path, name="out", frames=(24000, 12000)):
    out = tmp_path / name
    out.mkdir()
    for n, f in enumerate(frames, 1):
        put_wav(out, n, f)
    return out


def _run(plan, out, editor="resolve"):
    err = io.StringIO()
    code = run_pack(plan, FakeStdin(b""), out, err, editor)
    return code, err.getvalue()


def test_editor_run_ok_line_and_files(tmp_path):
    out = _out(tmp_path)
    code, text = _run(write_plan(tmp_path, _SCENES), out)
    assert code == 0
    assert text == _NOTE + _OK.format(d=out)
    assert text.count("\n") == 2
    assert sorted(os.listdir(out)) == ["audio", "resolve_timeline.otio", "scene_manifest.csv"]


def test_stdout_is_empty(tmp_path, capsys):
    out = _out(tmp_path)
    _run(write_plan(tmp_path, _SCENES), out)
    assert capsys.readouterr().out == ""


def test_manifest_bytes_equal_non_editor_run(tmp_path):
    plan = write_plan(tmp_path, _SCENES)
    a, b = _out(tmp_path, "a"), _out(tmp_path, "b")
    assert _run(plan, a)[0] == 0
    assert _run(plan, b, None)[0] == 0
    assert (a / "scene_manifest.csv").read_bytes() == (b / "scene_manifest.csv").read_bytes()


def test_timeline_equals_build_timeline(tmp_path):
    out = _out(tmp_path)
    _run(write_plan(tmp_path, _SCENES), out)
    scenes = [PlanScene(1, "One", "Hello."), PlanScene(2, "Two", "Hello.")]
    assert (out / "resolve_timeline.otio").read_bytes() == build_timeline(scenes, [24000, 12000])[0]


def test_non_editor_ok_line_unchanged_and_no_timeline(tmp_path):
    out = _out(tmp_path)
    (out / "resolve_timeline.otio").write_bytes(b"old")
    code, text = _run(write_plan(tmp_path, _SCENES), out, None)
    assert code == 0
    assert text == f"scenevoice pack: OK 2 scenes written to {out}/scene_manifest.csv\n"
    assert (out / "resolve_timeline.otio").read_bytes() == b"old"
    assert sorted(os.listdir(out)) == ["audio", "resolve_timeline.otio", "scene_manifest.csv"]


def test_non_editor_dir_holds_only_manifest_beside_existing(tmp_path):
    out = _out(tmp_path)
    _run(write_plan(tmp_path, _SCENES), out, None)
    assert sorted(os.listdir(out)) == ["audio", "scene_manifest.csv"]


def test_999_frame_wav_passes_without_flag_and_manifest_shows_0_042(tmp_path):
    out = _out(tmp_path, frames=(999, 12000))
    code, _ = _run(write_plan(tmp_path, _SCENES), out, None)
    assert code == 0
    assert "0.042" in (out / "scene_manifest.csv").read_text()


def test_zero_frame_rule_fails_editor_run_and_writes_nothing(tmp_path):
    out = _out(tmp_path, frames=(999, 12000))
    before = sorted(os.listdir(out))
    code, text = _run(write_plan(tmp_path, _SCENES), out)
    assert code == 1
    assert text.startswith("scenevoice pack: FAIL scene 1: audio/001.wav: ")
    assert sorted(os.listdir(out)) == before


def test_both_files_use_umask_mode(tmp_path):
    out = _out(tmp_path)
    old = os.umask(0o027)
    try:
        assert _run(write_plan(tmp_path, _SCENES), out)[0] == 0
    finally:
        os.umask(old)
    for name in ("scene_manifest.csv", "resolve_timeline.otio"):
        assert stat.S_IMODE(os.stat(out / name).st_mode) == 0o640


def test_determinism_across_fresh_directories_and_titles(tmp_path):
    scenes = [scene(1, "../x/é 中"), scene(2, "a/b")]
    plan = write_plan(tmp_path, scenes)
    a, b = _out(tmp_path, "a"), _out(tmp_path, "b")
    assert _run(plan, a)[0] == 0 and _run(plan, b)[0] == 0
    assert (a / "resolve_timeline.otio").read_bytes() == (b / "resolve_timeline.otio").read_bytes()
    assert sorted(os.listdir(a)) == ["audio", "resolve_timeline.otio", "scene_manifest.csv"]
