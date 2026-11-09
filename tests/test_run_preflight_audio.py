import json
import sys

from scenevoice.synth import PreflightResult, run_preflight

ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": "dummy-key-value",
}


def plan(tmp_path, n=2, valid=True):
    scenes = [{"ordinal": i, "title": "t", "body": "b"} for i in range(1, n + 1)]
    path = tmp_path / "plan.json"
    path.write_bytes(json.dumps({"scenes": scenes if valid else "bad"}).encode())
    return path


def run(tmp_path, plan_path, out, env=ENV):
    return run_preflight(plan_path, None, env, tmp_path / "absent.env", out)


def test_valid_plan_creates_audio_only(tmp_path):
    out = tmp_path / "out"
    assert isinstance(run(tmp_path, plan(tmp_path), out), PreflightResult)
    assert (out / "audio").is_dir()
    assert list(out.iterdir()) == [out / "audio"]
    assert list((out / "audio").iterdir()) == []


def test_invalid_plan_leaves_no_audio_folder(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    assert isinstance(run(tmp_path, plan(tmp_path, valid=False), out), str)
    assert not (out / "audio").exists()


def test_missing_env_leaves_no_audio_folder(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    result = run(tmp_path, plan(tmp_path), out, env={})
    assert isinstance(result, str) and "missing environment" in result
    assert not (out / "audio").exists()


def test_collision_message_uses_audio_prefix_in_plan_order(tmp_path):
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    for name in ("002.wav", "001.wav"):
        (out / "audio" / name).write_bytes(b"x")
    assert run(tmp_path, plan(tmp_path), out) == (
        "output already exists: audio/001.wav, audio/002.wav"
    )


def test_symlinked_audio_reported_before_collisions_and_nothing_created(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "001.wav").write_bytes(b"x")
    (out / "audio").symlink_to(elsewhere)
    assert run(tmp_path, plan(tmp_path), out) == "--out/audio exists and is not a real directory"
    assert sorted(p.name for p in elsewhere.iterdir()) == ["001.wav"]


def test_out_path_check_runs_before_audio_check(tmp_path):
    out = tmp_path / "out"
    out.write_bytes(b"x")
    assert run(tmp_path, plan(tmp_path), out) == "--out exists and is not a directory"


def test_flat_wav_neither_collides_nor_is_touched(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "001.wav").write_bytes(b"old")
    assert isinstance(run(tmp_path, plan(tmp_path), out), PreflightResult)
    assert (out / "001.wav").read_bytes() == b"old"


def test_probe_runs_on_audio_dir(tmp_path, monkeypatch):
    module = sys.modules["scenevoice.synth.prepare_out_dir"]
    seen = []
    real = module.probe_out_dir

    def spy(path):
        seen.append(str(path))
        return real(path)

    monkeypatch.setattr(module, "probe_out_dir", spy)
    out = tmp_path / "out"
    assert isinstance(run(tmp_path, plan(tmp_path), out), PreflightResult)
    assert seen == [str(out / "audio")]  # positive control: the spy was reached
