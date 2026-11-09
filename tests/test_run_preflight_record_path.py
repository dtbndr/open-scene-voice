import json
import os
import sys

from scenevoice.synth.preflight_result import PreflightResult
from scenevoice.synth.run_preflight import run_preflight

ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": "dummy-key-value",
}
RECORD = "synth_record.json exists and is not a regular file"
AUDIO = "DIR/audio exists and is not a directory"


def run(tmp_path, out_dir, scene=None):
    plan = tmp_path / "plan.json"
    scenes = [{"ordinal": i, "title": "t", "body": "b"} for i in (1, 2, 3)]
    plan.write_bytes(json.dumps({"scenes": scenes}).encode("utf-8"))
    return run_preflight(plan, None, ENV, tmp_path / "absent.env", out_dir, scene=scene)


def test_full_run_refuses_directory_record_and_creates_nothing(tmp_path):
    out = tmp_path / "out"
    (out / "synth_record.json").mkdir(parents=True)
    assert run(tmp_path, out) == RECORD
    assert sorted(p.name for p in out.iterdir()) == ["synth_record.json"]


def test_collision_is_reported_before_record(tmp_path):
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    (out / "audio" / "002.wav").write_bytes(b"x")
    (out / "synth_record.json").mkdir()
    assert run(tmp_path, out) == "output already exists: audio/002.wav"


def test_audio_symlink_is_reported_before_record(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (tmp_path / "elsewhere").mkdir()
    os.symlink(tmp_path / "elsewhere", out / "audio")
    (out / "synth_record.json").mkdir()
    result = run(tmp_path, out)
    assert isinstance(result, str) and result != RECORD and "audio" in result


def test_scene_mode_refuses_non_regular_record(tmp_path):
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    (out / "synth_record.json").mkdir()
    assert run(tmp_path, out, scene=2) == RECORD


def test_scene_mode_target_is_reported_before_record(tmp_path):
    out = tmp_path / "out"
    (out / "audio" / "002.wav").mkdir(parents=True)
    (out / "synth_record.json").mkdir()
    assert run(tmp_path, out, scene=2) == "002.wav exists and is not a regular file"


def test_regular_record_is_left_byte_identical_by_both_modes(tmp_path):
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    record = out / "synth_record.json"
    record.write_bytes(b"\xff not json")
    os.utime(record, (1, 1))
    for scene in (None, 2):
        assert isinstance(run(tmp_path, out, scene=scene), PreflightResult)
        assert record.read_bytes() == b"\xff not json"
        assert os.stat(record).st_mtime == 1


def test_record_check_runs_between_target_and_probe(tmp_path, monkeypatch):
    module = sys.modules["scenevoice.synth.run_preflight"]
    calls = []
    for name in ("check_scene_target", "check_record_path", "probe_out_dir"):
        real = getattr(module, name)
        monkeypatch.setattr(
            module, name, lambda *a, _n=name, _r=real: calls.append(_n) or _r(*a)
        )
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    assert isinstance(run(tmp_path, out, scene=2), PreflightResult)
    assert calls == ["check_scene_target", "check_record_path", "probe_out_dir"]
