import json
import sys

from scenevoice.synth import AUDIO_DIR, PreflightResult
from scenevoice.synth.run_preflight import run_preflight

MODULE = "scenevoice.synth.run_preflight"
ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": "dummy-key-value",
}
NOT_DIR = "--out does not exist or is not a directory"
NO_AUDIO = "--out/audio does not exist or is not a directory"


def run(tmp_path, out_dir, scene=2, env=ENV):
    plan = tmp_path / "plan.json"
    scenes = [{"ordinal": i, "title": "t", "body": f"b{i}"} for i in (1, 2, 3)]
    plan.write_text(json.dumps({"scenes": scenes}))
    return run_preflight(plan, None, env, tmp_path / "absent.env", out_dir, scene=scene)


def test_missing_out_reported_before_audio(tmp_path):
    assert run(tmp_path, tmp_path / "nope") == NOT_DIR


def test_missing_audio_reported_and_nothing_created(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    assert run(tmp_path, out) == NO_AUDIO
    assert list(out.iterdir()) == []


def test_symlinked_audio_refused_even_with_bad_target_behind_it(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere" / "002.wav").mkdir()
    (out / AUDIO_DIR).symlink_to(tmp_path / "elsewhere")
    assert run(tmp_path, out) == NO_AUDIO


def test_audio_reported_before_target(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "002.wav").mkdir()  # flat, ignored; audio missing wins
    assert run(tmp_path, out) == NO_AUDIO


def test_target_under_audio_refused_with_bare_name(tmp_path):
    out = tmp_path / "out"
    (out / "audio" / "002.wav").mkdir(parents=True)
    assert run(tmp_path, out) == "002.wav exists and is not a regular file"


def test_flat_target_is_ignored_and_probe_runs_on_audio(tmp_path, monkeypatch):
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    (out / "002.wav").mkdir()
    probed = []
    module = sys.modules[MODULE]
    real = module.probe_out_dir
    monkeypatch.setattr(module, "probe_out_dir", lambda d: probed.append(d) or real(d))
    assert isinstance(run(tmp_path, out), PreflightResult)
    assert [str(p) for p in probed] == [str(out / "audio")]
    assert sorted(p.name for p in (out / "audio").iterdir()) == []


def test_check_order_out_audio_target_probe(tmp_path, monkeypatch):
    module = sys.modules[MODULE]
    calls = []
    for name in ("check_out_dir_exists", "check_audio_dir_scene", "check_scene_target",
                 "probe_out_dir"):
        real = getattr(module, name)
        monkeypatch.setattr(
            module, name, lambda *a, _n=name, _r=real: calls.append(_n) or _r(*a)
        )
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    assert isinstance(run(tmp_path, out), PreflightResult)
    assert calls == ["check_out_dir_exists", "check_audio_dir_scene", "check_scene_target",
                     "probe_out_dir"]


def test_bad_scene_number_and_missing_env_leave_nothing(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    assert "out of range" in run(tmp_path, out, scene=9)
    assert "missing environment variables" in run(tmp_path, out, env={})
    assert list(out.iterdir()) == []
