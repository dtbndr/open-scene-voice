import io
import json
import os
import stat
import sys

import pytest

from scenevoice.synth import PlanScene, wav_name
from scenevoice.synth.preflight_result import PreflightResult
from scenevoice.synth.run_preflight import run_preflight

MODULE = "scenevoice.synth.run_preflight"
ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": "dummy-key-value",
}
NOT_DIR = "--out does not exist or is not a directory"


def plan_bytes(n=3, bodies=None):
    scenes = [
        {"ordinal": i, "title": "t", "body": (bodies or {}).get(i, "b")}
        for i in range(1, n + 1)
    ]
    return json.dumps({"scenes": scenes}).encode("utf-8")


class FakeStdin:
    def __init__(self, data=b"", tty=False):
        self.buffer = io.BytesIO(data)
        self.tty = tty

    def isatty(self):
        return self.tty


@pytest.fixture
def out(tmp_path):
    path = tmp_path / "out"
    (path / "audio").mkdir(parents=True)
    return path


def plan_file(tmp_path, data):
    path = tmp_path / "plan.json"
    path.write_bytes(data)
    return path


def run(tmp_path, out_dir, scene=2, data=None, env=ENV, stdin=None, plan=True):
    path = plan_file(tmp_path, plan_bytes() if data is None else data) if plan else None
    return run_preflight(
        path, stdin, env, tmp_path / "absent.env", out_dir, scene=scene
    )


def test_returns_selected_scene_total_and_env(tmp_path, out):
    result = run(tmp_path, out, scene=2)
    assert isinstance(result, PreflightResult)
    assert result.scenes == [PlanScene(2, "t", "b")]
    assert result.total == 3
    assert result.env == ENV


def test_total_has_default_for_existing_constructions():
    assert PreflightResult([], {}).total == 0


def test_full_run_reports_total(tmp_path):
    result = run(tmp_path, tmp_path / "new", scene=None)
    assert isinstance(result, PreflightResult)
    assert result.total == 3
    assert len(result.scenes) == 3


def test_terminal_stdin_checked_first(tmp_path, out):
    result = run(tmp_path, out, plan=False, stdin=FakeStdin(plan_bytes(), tty=True))
    assert result == "no PLAN given and stdin is a terminal"


def test_bad_plan_reported_before_out_of_range_scene(tmp_path, out):
    result = run(tmp_path, out, scene=99, data=b"not json")
    assert isinstance(result, str)
    assert "out of range" not in result


def test_out_of_range_scene_reported_before_missing_env(tmp_path, out):
    result = run(tmp_path, out, scene=4, env={})
    assert result == "--scene 4 is out of range (the plan has 3 scenes)"


@pytest.mark.parametrize("scene", [0, -1])
def test_zero_and_negative_scene_out_of_range(tmp_path, out, scene):
    result = run(tmp_path, out, scene=scene)
    assert result == f"--scene {scene} is out of range (the plan has 3 scenes)"


def test_missing_env_reported_before_out_dir(tmp_path):
    result = run(tmp_path, tmp_path / "absent", scene=1, env={})
    assert isinstance(result, str)
    assert result.startswith("missing environment variables: ")


def test_over_limit_body_in_other_scene_fails(tmp_path, out):
    data = plan_bytes(3, {3: "x" * 8001})
    result = run(tmp_path, out, scene=1, data=data)
    assert isinstance(result, str)
    assert "8000" in result


def test_more_than_999_scenes_fails(tmp_path, out):
    result = run(tmp_path, out, scene=1, data=plan_bytes(1000))
    assert isinstance(result, str)
    assert not isinstance(result, PreflightResult)


def test_missing_out_fails_and_creates_nothing(tmp_path):
    missing = tmp_path / "missing" / "deeper"
    assert run(tmp_path, missing) == NOT_DIR
    assert not (tmp_path / "missing").exists()


def test_regular_file_at_out_fails(tmp_path):
    file_out = tmp_path / "file"
    file_out.write_bytes(b"x")
    assert run(tmp_path, file_out) == NOT_DIR


def test_existing_directory_passes_and_probe_leaves_nothing(tmp_path, out):
    assert isinstance(run(tmp_path, out), PreflightResult)
    assert list((out / "audio").iterdir()) == []


def test_absent_and_regular_file_targets_pass(tmp_path, out):
    (out / "audio" / wav_name(2)).write_bytes(b"old")
    assert isinstance(run(tmp_path, out, scene=2), PreflightResult)
    assert (out / "audio" / wav_name(2)).read_bytes() == b"old"
    assert isinstance(run(tmp_path, out, scene=1), PreflightResult)


def test_directory_target_refused(tmp_path, out):
    (out / "audio" / wav_name(2)).mkdir()
    assert run(tmp_path, out, scene=2) == "002.wav exists and is not a regular file"


def test_symlink_targets_refused(tmp_path, out):
    real = tmp_path / "real.wav"
    real.write_bytes(b"x")
    (out / "audio" / wav_name(1)).symlink_to(real)
    (out / "audio" / wav_name(2)).symlink_to(tmp_path / "gone.wav")
    assert run(tmp_path, out, scene=1) == "001.wav exists and is not a regular file"
    assert run(tmp_path, out, scene=2) == "002.wav exists and is not a regular file"


def test_other_scenes_files_do_not_fail(tmp_path, out):
    for n in (1, 3):
        (out / "audio" / wav_name(n)).write_bytes(b"old")
    assert isinstance(run(tmp_path, out, scene=2), PreflightResult)


def test_non_directory_out_reported_not_raised_before_target(tmp_path):
    # order pin: a path under a regular file would make lstat raise ENOTDIR if the target
    # check ran first; the out-dir check must report first
    file_out = tmp_path / "file"
    file_out.write_bytes(b"x")
    assert run(tmp_path, file_out, scene=1) == NOT_DIR


def test_order_out_dir_check_before_target_check(tmp_path, monkeypatch):
    module = sys.modules[MODULE]
    calls = []
    real_dir, real_target = module.check_out_dir_exists, module.check_scene_target

    def dir_spy(*a, **k):
        calls.append("dir")
        return real_dir(*a, **k)

    def target_spy(*a, **k):
        calls.append("target")
        return real_target(*a, **k)

    monkeypatch.setattr(module, "check_out_dir_exists", dir_spy)
    monkeypatch.setattr(module, "check_scene_target", target_spy)
    out_dir = tmp_path / "out"
    (out_dir / "audio").mkdir(parents=True)
    assert isinstance(run(tmp_path, out_dir, scene=1), PreflightResult)
    assert calls == ["dir", "target"]  # positive control: both fakes ran, in order
    calls.clear()
    assert run(tmp_path, tmp_path / "nope", scene=1) == NOT_DIR
    assert calls == ["dir"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_probe_failure_refused(tmp_path, out):
    (out / "audio").chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        result = run(tmp_path, out)
    finally:
        (out / "audio").chmod(stat.S_IRWXU)
    assert result == "output directory is not writable"


def test_scene_mode_skips_collision_check_and_creation(tmp_path, out, monkeypatch):
    module = sys.modules[MODULE]
    calls = []
    monkeypatch.setattr(module, "find_collisions", lambda *a: calls.append("c") or [])
    monkeypatch.setattr(
        module, "prepare_out_dir", lambda *a: calls.append("p")
    )
    assert isinstance(run(tmp_path, out), PreflightResult)
    assert calls == []
    # positive control: the full run uses both
    assert isinstance(run(tmp_path, out, scene=None), PreflightResult)
    assert calls == ["c", "p"]


def test_no_scene_collision_still_fails(tmp_path, out):
    (out / "audio" / wav_name(2)).write_bytes(b"old")
    assert run(tmp_path, out, scene=None) == "output already exists: audio/002.wav"


def test_no_scene_creates_missing_out(tmp_path):
    target = tmp_path / "new" / "deep"
    assert isinstance(run(tmp_path, target, scene=None), PreflightResult)
    assert target.is_dir()
