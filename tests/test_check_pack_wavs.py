import os

import pytest
from wav_helper import make_wav

from scenevoice.pack import check_pack_wavs
from scenevoice.synth import PlanScene


def _scenes(n):
    return [PlanScene(i, f"T{i}", "b") for i in range(1, n + 1)]


def _put(tmp_path, ordinal, data):
    (tmp_path / "audio").mkdir(exist_ok=True)
    (tmp_path / "audio" / f"{ordinal:03d}.wav").write_bytes(data)


def _good(tmp_path, n=3, frames=(10, 20, 30)):
    for i in range(1, n + 1):
        _put(tmp_path, i, make_wav(frames[i - 1]))


def _assert_names(result, ordinal):
    assert isinstance(result, str)
    assert f"scene {ordinal}" in result
    assert f"audio/{ordinal:03d}.wav" in result


def test_all_valid_returns_frames_in_plan_order(tmp_path):
    _good(tmp_path)
    assert check_pack_wavs(_scenes(3), tmp_path) == [10, 20, 30]


def test_missing_scene_named(tmp_path):
    _good(tmp_path)
    (tmp_path / "audio" / "002.wav").unlink()
    _assert_names(check_pack_wavs(_scenes(3), tmp_path), 2)


def test_directory_named_wav_rejected(tmp_path):
    _good(tmp_path)
    (tmp_path / "audio" / "002.wav").unlink()
    (tmp_path / "audio" / "002.wav").mkdir()
    _assert_names(check_pack_wavs(_scenes(3), tmp_path), 2)


def test_symlink_to_valid_wav_rejected(tmp_path):
    _good(tmp_path)
    (tmp_path / "audio" / "002.wav").unlink()
    _put(tmp_path, 9, make_wav())
    try:
        (tmp_path / "audio" / "002.wav").symlink_to(tmp_path / "audio" / "009.wav")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported")
    _assert_names(check_pack_wavs(_scenes(3), tmp_path), 2)


@pytest.mark.parametrize(
    "data",
    [
        make_wav(rate=16000),
        make_wav(channels=2),
        make_wav(width=1),
        make_wav(frames=0),
        make_wav(frames=10)[:-4],
        b"not a wav at all",
    ],
    ids=["rate", "stereo", "8bit", "zero-frames", "truncated", "garbage"],
)
def test_invalid_wav_named(tmp_path, data):
    _good(tmp_path)
    _put(tmp_path, 2, data)
    _assert_names(check_pack_wavs(_scenes(3), tmp_path), 2)


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0, reason="needs a non-root user")
def test_unreadable_wav_is_a_message_not_a_traceback(tmp_path):
    _good(tmp_path)
    path = tmp_path / "audio" / "002.wav"
    path.chmod(0)
    try:
        _assert_names(check_pack_wavs(_scenes(3), tmp_path), 2)
    finally:
        path.chmod(0o644)


def test_first_failing_scene_stops_checks(tmp_path):
    _good(tmp_path)
    _put(tmp_path, 2, b"bad")
    _put(tmp_path, 3, b"bad")
    result = check_pack_wavs(_scenes(3), tmp_path)
    _assert_names(result, 2)
    assert "003.wav" not in result


def test_extra_and_stale_files_ignored(tmp_path):
    _good(tmp_path)
    _put(tmp_path, 7, b"junk")
    (tmp_path / "notes.txt").write_bytes(b"hi")
    assert check_pack_wavs(_scenes(3), tmp_path) == [10, 20, 30]
