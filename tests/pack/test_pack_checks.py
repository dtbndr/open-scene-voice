"""check_pack_wavs is a thin wrapper over synth.load_scene_wavs.

The per-file rules (missing, directory, symlink, unreadable, invalid WAV kinds, first failure
stops, min_frames boundary and order) are pinned in tests/synth/test_load_scene_wavs.py and
test_read_wav_frames.py; here only the wrapper's own contract is pinned.
"""

import os
import sys

import pytest
from pack_run_helper import put_wav
from wav_helper import make_wav

from scenevoice.pack import (
    SAMPLE_FRAMES_PER_TIMELINE_FRAME,
    check_no_collision,
    check_no_timeline_collision,
    check_pack_audio_dir,
    check_pack_wavs,
)
from scenevoice.synth import PlanScene

CHECKS = [
    pytest.param(check_no_collision, "scene_manifest.csv", id="manifest"),
    pytest.param(check_no_timeline_collision, "resolve_timeline.otio", id="timeline"),
]


def _refused(check, name, directory):
    message = check(directory)
    assert isinstance(message, str)
    assert name in message


@pytest.mark.parametrize(("check", "name"), CHECKS)
def test_absent_path_is_clear(tmp_path, check, name):
    assert check(tmp_path) is None


@pytest.mark.parametrize(("check", "name"), CHECKS)
@pytest.mark.parametrize("kind", ["empty-file", "dangling-symlink"])
def test_anything_at_the_path_collides(tmp_path, check, name, kind):
    target = tmp_path / name
    if kind == "empty-file":
        target.write_bytes(b"")
    elif kind == "directory":
        target.mkdir()
    elif kind == "symlink":
        (tmp_path / "real").write_bytes(b"x")
        os.symlink(tmp_path / "real", target)
    else:
        os.symlink(tmp_path / "gone", target)
    _refused(check, name, tmp_path)


def _symlink(link, target, is_dir):
    try:
        link.symlink_to(target, target_is_directory=is_dir)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported")


def test_real_audio_directory_passes(tmp_path):
    (tmp_path / "audio").mkdir()
    assert check_pack_audio_dir(tmp_path) is None


def test_missing_audio_says_directory_does_not_exist(tmp_path):
    message = check_pack_audio_dir(tmp_path)
    assert message == f"{tmp_path}/audio: directory does not exist"


def test_regular_file_says_not_a_directory(tmp_path):
    (tmp_path / "audio").write_bytes(b"x")
    assert check_pack_audio_dir(tmp_path) == f"{tmp_path}/audio: not a directory"


def test_symlink_to_directory_is_refused(tmp_path):
    (tmp_path / "real").mkdir()
    _symlink(tmp_path / "audio", tmp_path / "real", True)
    assert check_pack_audio_dir(tmp_path) == f"{tmp_path}/audio: not a directory"


def test_dangling_symlink_is_refused(tmp_path):
    _symlink(tmp_path / "audio", tmp_path / "nowhere", False)
    assert check_pack_audio_dir(tmp_path) == f"{tmp_path}/audio: not a directory"


def test_symlinked_dir_with_real_audio_passes(tmp_path):
    real = tmp_path / "real"
    (real / "audio").mkdir(parents=True)
    _symlink(tmp_path / "link", real, True)
    assert check_pack_audio_dir(tmp_path / "link") is None


def test_unexpected_oserror_says_cannot_be_checked(tmp_path, monkeypatch):
    module = sys.modules["scenevoice.pack.check_pack_audio_dir"]
    reached = []

    def boom(path):
        reached.append(path)
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(module.os, "lstat", boom)
    message = check_pack_audio_dir(tmp_path)
    assert reached, "positive control: the patched lstat was reached"
    assert message == f"{tmp_path}/audio: cannot be checked (Permission denied)"


MIN = SAMPLE_FRAMES_PER_TIMELINE_FRAME


def _scenes(n):
    return [PlanScene(i, f"T{i}", "b") for i in range(1, n + 1)]


def _good(tmp_path, n=3, frames=(10, 20, 30)):
    for i in range(1, n + 1):
        put_wav(tmp_path, i, frames[i - 1])


def _assert_names(result, ordinal):
    assert isinstance(result, str)
    assert f"scene {ordinal}" in result
    assert f"audio/{ordinal:03d}.wav" in result


def test_all_valid_returns_frames_in_plan_order(tmp_path):
    _good(tmp_path)
    assert check_pack_wavs(_scenes(3), tmp_path) == [10, 20, 30]


def test_failure_message_names_scene_and_file(tmp_path):
    _good(tmp_path)
    (tmp_path / "audio" / "002.wav").unlink()
    _assert_names(check_pack_wavs(_scenes(3), tmp_path), 2)


def test_extra_and_stale_files_ignored(tmp_path):
    _good(tmp_path)
    (tmp_path / "audio" / "007.wav").write_bytes(b"junk")
    (tmp_path / "notes.txt").write_bytes(b"hi")
    assert check_pack_wavs(_scenes(3), tmp_path) == [10, 20, 30]


def test_min_frames_is_forwarded_and_off_by_default(tmp_path):
    (tmp_path / "audio").mkdir()
    (tmp_path / "audio" / "001.wav").write_bytes(make_wav(MIN - 1))
    _assert_names(check_pack_wavs(_scenes(1), tmp_path, min_frames=MIN), 1)
    assert check_pack_wavs(_scenes(1), tmp_path) == [MIN - 1]
