import io
import os

from pack_run_helper import FakeStdin, put_wav, scene, write_plan

from scenevoice.pack import run_pack

_SCENES = [scene(1, "One"), scene(2, "Two")]


def _out(tmp_path, wavs=(1, 2), frames=24000):
    out = tmp_path / "out"
    out.mkdir()
    for n in wavs:
        put_wav(out, n, frames)
    return out


def _run(plan, out):
    err = io.StringIO()
    code = run_pack(plan, FakeStdin(b""), out, err, "resolve")
    return code, err.getvalue()


def _snapshot(out):
    return {p.name: p.read_bytes() for p in out.iterdir() if p.is_file() and not p.is_symlink()}


def test_manifest_collision_beats_timeline_collision(tmp_path):
    out = _out(tmp_path)
    (out / "scene_manifest.csv").write_bytes(b"m")
    (out / "resolve_timeline.otio").write_bytes(b"t")
    code, text = _run(write_plan(tmp_path, _SCENES), out)
    assert code == 1 and "scene_manifest.csv" in text and "resolve_timeline" not in text


def test_timeline_collision_beats_missing_wav(tmp_path):
    out = _out(tmp_path, wavs=(1,))
    (out / "resolve_timeline.otio").write_bytes(b"t")
    code, text = _run(write_plan(tmp_path, _SCENES), out)
    assert code == 1 and "resolve_timeline.otio" in text and "002.wav" not in text
    assert (out / "resolve_timeline.otio").read_bytes() == b"t"


def test_plan_error_beats_timeline_collision(tmp_path):
    out = _out(tmp_path)
    (out / "resolve_timeline.otio").write_bytes(b"t")
    plan = tmp_path / "plan.json"
    plan.write_bytes(b"not json")
    code, text = _run(plan, out)
    assert code == 1 and "resolve_timeline" not in text


def test_missing_audio_dir_beats_timeline_collision(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "resolve_timeline.otio").write_bytes(b"t")
    code, text = _run(write_plan(tmp_path, _SCENES), out)
    assert code == 1 and "audio" in text and "resolve_timeline" not in text


def test_timeline_collision_beats_zero_frame_scene(tmp_path):
    out = _out(tmp_path, frames=999)
    (out / "resolve_timeline.otio").write_bytes(b"t")
    code, text = _run(write_plan(tmp_path, _SCENES), out)
    assert code == 1 and "resolve_timeline.otio" in text and "001.wav" not in text


def test_failures_write_nothing_and_keep_colliding_bytes(tmp_path):
    out = _out(tmp_path, wavs=(1,))
    (out / "resolve_timeline.otio").write_bytes(b"t")
    before = _snapshot(out)
    _run(write_plan(tmp_path, _SCENES), out)
    assert _snapshot(out) == before and sorted(os.listdir(out)) == sorted(list(before) + ["audio"])
