"""run_preflight steps 5-7 for a full run: output checks in order, collisions, the audio folder, the result."""

import os
import stat

import pytest
from preflight_helper import ENV, preflight, spy_calls

from scenevoice.synth import PlanScene, RecordSettings, wav_name
from scenevoice.synth.preflight_result import PreflightResult

FULL_ORDER = [
    "read_plan_input", "load_plan", "check_limits", "resolve_env",
    "check_out_path", "check_audio_dir_full", "find_collisions", "check_record_path",
    "prepare_out_dir",
]  # fmt: skip


def test_full_checks_run_in_contract_order(tmp_path, monkeypatch):
    calls = spy_calls(monkeypatch, *FULL_ORDER)
    result = preflight(tmp_path, tmp_path / "out")
    assert isinstance(result, PreflightResult)
    assert calls == FULL_ORDER


def test_full_fresh_out_gets_only_an_empty_audio_folder(tmp_path):
    out = tmp_path / "fresh"
    result = preflight(tmp_path, out, n=2)
    assert isinstance(result, PreflightResult)
    assert result.scenes == [PlanScene(1, "t", "b"), PlanScene(2, "t", "b")]
    assert result.env == ENV and result.total == 2
    assert os.listdir(out) == ["audio"] and os.listdir(out / "audio") == []


def test_full_collisions_are_named_in_plan_order_and_nothing_is_created(tmp_path, monkeypatch):
    calls = spy_calls(monkeypatch, "prepare_out_dir")
    out = tmp_path / "existing"
    (out / "audio").mkdir(parents=True)
    for name in ("002.wav", "001.wav"):
        (out / "audio" / name).write_bytes(b"old")
    result = preflight(tmp_path, out)
    assert result == "output already exists: audio/001.wav, audio/002.wav"
    assert calls == [] and sorted(os.listdir(out)) == ["audio"]
    assert sorted(os.listdir(out / "audio")) == ["001.wav", "002.wav"]


def test_full_stale_and_flat_wavs_are_neither_collisions_nor_touched(tmp_path):
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    (out / "audio" / "007.wav").write_bytes(b"stale")
    (out / "001.wav").write_bytes(b"flat")
    assert isinstance(preflight(tmp_path, out), PreflightResult)
    assert (out / "audio" / "007.wav").read_bytes() == b"stale"
    assert (out / "001.wav").read_bytes() == b"flat"


def test_full_out_that_is_a_regular_file_is_refused_untouched(tmp_path, monkeypatch):
    calls = spy_calls(monkeypatch, "prepare_out_dir")
    out = tmp_path / "afile"
    out.write_bytes(b"x")
    result = preflight(tmp_path, out)
    assert isinstance(result, str) and "--out" in result
    assert calls == [] and out.read_bytes() == b"x"


def test_full_symlinked_audio_is_refused_before_collisions_and_nothing_is_created(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "001.wav").write_bytes(b"x")
    (out / "audio").symlink_to(elsewhere)
    result = preflight(tmp_path, out)
    assert isinstance(result, str) and "--out/audio" in result
    assert sorted(p.name for p in elsewhere.iterdir()) == ["001.wav"]


def test_full_non_regular_record_is_refused_and_creates_nothing(tmp_path):
    out = tmp_path / "out"
    (out / "synth_record.json").mkdir(parents=True)
    result = preflight(tmp_path, out)
    assert isinstance(result, str) and result.startswith("synth_record.json")
    assert sorted(p.name for p in out.iterdir()) == ["synth_record.json"]


def test_full_regular_record_is_left_byte_identical(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    record = out / "synth_record.json"
    record.write_bytes(b"\xff not json")
    os.utime(record, (1, 1))
    assert isinstance(preflight(tmp_path, out), PreflightResult)
    assert record.read_bytes() == b"\xff not json" and os.stat(record).st_mtime == 1


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0, reason="permissions not enforced for root"
)
@pytest.mark.parametrize("audio_exists", [True, False], ids=["audio-unwritable", "out-unwritable"])
def test_full_unwritable_directory_is_refused_leaving_nothing(tmp_path, audio_exists):
    out = tmp_path / "out"
    target = out / "audio" if audio_exists else out
    (out / "audio" if audio_exists else out).mkdir(parents=True)
    target.chmod(0o500)
    try:
        result = preflight(tmp_path, out)
        listing = os.listdir(target)
    finally:
        target.chmod(0o700)
    assert isinstance(result, str) and not result.startswith("scenevoice synth")
    assert "dummy-key-value" not in result
    assert listing == []


def test_full_dangling_symlink_out_is_refused_without_creating_the_target(tmp_path):
    out = tmp_path / "link"
    out.symlink_to(tmp_path / "missing")
    assert isinstance(preflight(tmp_path, out), str)
    assert not (tmp_path / "missing").exists()


SCENE_ORDER = [
    "read_plan_input", "load_plan", "check_limits", "check_scene", "resolve_env",
    "check_out_dir_exists", "check_audio_dir_scene", "check_scene_target", "check_record_path",
    "load_record", "probe_out_dir",
]  # fmt: skip


SETTINGS = RecordSettings("Callirrhoe", "gemini-3.8-flash-tts", "en-GB", None)


@pytest.fixture
def out(tmp_path):
    path = tmp_path / "out"
    (path / "audio").mkdir(parents=True)
    return path


def scene_run(tmp_path, out_dir, **kw):
    kw.setdefault("scene", 2)
    return preflight(tmp_path, out_dir, **kw)


def test_scene_checks_run_in_contract_order(tmp_path, out, monkeypatch):
    calls = spy_calls(monkeypatch, *SCENE_ORDER)
    assert isinstance(scene_run(tmp_path, out, settings=SETTINGS), PreflightResult)
    assert calls == SCENE_ORDER


def test_scene_result_holds_selected_scene_total_env_and_whole_plan(tmp_path, out):
    result = scene_run(tmp_path, out)
    assert isinstance(result, PreflightResult)
    assert result.scenes == [PlanScene(2, "t", "b")]
    assert result.total == 3 and result.env == ENV
    assert result.plan == tuple(PlanScene(i, "t", "b") for i in (1, 2, 3))


@pytest.mark.parametrize(
    "kw",
    [{"scene": 9}, {"env": {}}],
    ids=["bad-scene", "missing-keys"],
)
def test_scene_early_failures_leave_the_directory_untouched(tmp_path, kw):
    out = tmp_path / "out"
    out.mkdir()
    result = scene_run(tmp_path, out, **kw)
    assert isinstance(result, str)
    assert "out of range" in result or result.startswith("Missing:")
    assert list(out.iterdir()) == []


@pytest.mark.parametrize(
    "kw",
    [{"bodies": {3: "x" * 8001}}, {"n": 1000}],
    ids=["other-scene-over-limit", "1000-scenes"],
)
def test_scene_limits_cover_the_whole_plan_not_just_the_selected_scene(tmp_path, out, kw):
    result = scene_run(tmp_path, out, scene=1, **kw)
    assert isinstance(result, str) and not isinstance(result, PreflightResult)


def test_scene_missing_out_is_refused_and_nothing_is_created(tmp_path):
    result = scene_run(tmp_path, tmp_path / "missing" / "deeper")
    assert isinstance(result, str) and "--out" in result
    assert not (tmp_path / "missing").exists()


def test_scene_missing_audio_dir_is_refused_and_not_created(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "002.wav").mkdir()  # flat, ignored
    result = scene_run(tmp_path, out)
    assert isinstance(result, str) and "--out/audio" in result
    assert [p.name for p in out.iterdir()] == ["002.wav"]


def test_scene_symlinked_audio_dir_is_refused_even_with_a_bad_target_behind_it(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (tmp_path / "elsewhere" / "002.wav").mkdir(parents=True)
    (out / "audio").symlink_to(tmp_path / "elsewhere")
    result = scene_run(tmp_path, out)
    assert isinstance(result, str) and "--out/audio" in result


def test_scene_non_regular_target_is_refused_naming_the_bare_file(tmp_path, out):
    (out / "audio" / wav_name(2)).mkdir()
    result = scene_run(tmp_path, out)
    assert isinstance(result, str) and result.startswith("002.wav")


def test_scene_absent_and_regular_targets_pass_untouched_and_flat_files_are_ignored(tmp_path, out):
    (out / "002.wav").mkdir()  # flat, ignored
    assert isinstance(scene_run(tmp_path, out, scene=2), PreflightResult)
    (out / "audio" / wav_name(2)).write_bytes(b"old")
    assert isinstance(scene_run(tmp_path, out, scene=2), PreflightResult)
    assert (out / "audio" / wav_name(2)).read_bytes() == b"old"
    assert sorted(p.name for p in (out / "audio").iterdir()) == ["002.wav"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_scene_unwritable_audio_dir_is_refused(tmp_path, out):
    (out / "audio").chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        result = scene_run(tmp_path, out)
    finally:
        (out / "audio").chmod(stat.S_IRWXU)
    assert result == "output directory is not writable"


def test_scene_scene_mode_skips_collision_check_and_creation(tmp_path, out, monkeypatch):
    calls = spy_calls(monkeypatch, "find_collisions", "prepare_out_dir")
    (out / "audio" / wav_name(2)).write_bytes(b"old")
    assert isinstance(scene_run(tmp_path, out), PreflightResult)
    assert calls == []
    assert isinstance(scene_run(tmp_path, out, scene=None), str)  # a full run does collide
    assert calls == ["find_collisions"]
