import sys

import pytest
from wav_helper import make_wav

from scenevoice.synth import PlanScene, SceneWav, load_scene_wavs, read_wav_frames


def _scenes(n):
    return [PlanScene(i, f"T{i}", "b") for i in range(1, n + 1)]


def _put(tmp_path, ordinal, data):
    (tmp_path / "audio").mkdir(exist_ok=True)
    (tmp_path / "audio" / f"{ordinal:03d}.wav").write_bytes(data)


def _fails(result, ordinal, reason=None):
    assert isinstance(result, str)
    assert result.startswith(f"scene {ordinal}: audio/{ordinal:03d}.wav: ")
    if reason:
        assert reason in result


def test_returns_bytes_and_frames_in_plan_order(tmp_path):
    wavs = [make_wav(10), make_wav(20), make_wav(30)]
    for i, w in enumerate(wavs, 1):
        _put(tmp_path, i, w)
    result = load_scene_wavs(_scenes(3), tmp_path, 0)
    assert result == [SceneWav(w, f) for w, f in zip(wavs, (10, 20, 30), strict=True)]
    assert [r.data for r in result] == wavs


def test_scene_wav_is_frozen():
    with pytest.raises(AttributeError):
        SceneWav(b"x", 1).frames = 2  # type: ignore[misc]


def test_missing_file(tmp_path):
    _put(tmp_path, 1, make_wav(10))
    _fails(load_scene_wavs(_scenes(2), tmp_path, 0), 2, "not a regular file")


def test_directory_in_place_of_file(tmp_path):
    (tmp_path / "audio" / "001.wav").mkdir(parents=True)
    _fails(load_scene_wavs(_scenes(1), tmp_path, 0), 1, "not a regular file")


def test_symlink_refused(tmp_path):
    _put(tmp_path, 2, make_wav(10))
    (tmp_path / "audio" / "001.wav").symlink_to(tmp_path / "audio" / "002.wav")
    _fails(load_scene_wavs(_scenes(1), tmp_path, 0), 1, "not a regular file")


def test_unreadable_file(tmp_path):
    import os

    if os.geteuid() == 0:
        pytest.skip("root reads anything")
    _put(tmp_path, 1, make_wav(10))
    p = tmp_path / "audio" / "001.wav"
    p.chmod(0)
    try:
        _fails(load_scene_wavs(_scenes(1), tmp_path, 0), 1, "cannot be read")
    finally:
        p.chmod(0o644)


def test_non_wav(tmp_path):
    _put(tmp_path, 1, b"not a wav at all")
    _fails(load_scene_wavs(_scenes(1), tmp_path, 0), 1)


def test_wrong_rate(tmp_path):
    _put(tmp_path, 1, make_wav(10, rate=16000))
    _fails(load_scene_wavs(_scenes(1), tmp_path, 0), 1)


def test_empty_data_section(tmp_path):
    _put(tmp_path, 1, make_wav(0))
    _fails(load_scene_wavs(_scenes(1), tmp_path, 0), 1)


def test_truncated_file(tmp_path):
    _put(tmp_path, 1, make_wav(100)[:-50])
    _fails(load_scene_wavs(_scenes(1), tmp_path, 0), 1)


def test_first_failure_stops_the_checks(tmp_path):
    _put(tmp_path, 1, make_wav(10))
    _put(tmp_path, 2, b"junk")
    _put(tmp_path, 3, b"junk too")
    result = load_scene_wavs(_scenes(3), tmp_path, 0)
    _fails(result, 2)
    assert "scene 3" not in result


def test_min_frames_rejects_999_and_names_scene_and_file(tmp_path):
    _put(tmp_path, 1, make_wav(999))
    _fails(load_scene_wavs(_scenes(1), tmp_path, 1000), 1, "1000")


def test_min_frames_accepts_1000(tmp_path):
    _put(tmp_path, 1, make_wav(1000))
    result = load_scene_wavs(_scenes(1), tmp_path, 1000)
    assert isinstance(result, list) and result[0].frames == 1000


def test_min_frames_zero_accepts_999(tmp_path):
    _put(tmp_path, 1, make_wav(999))
    result = load_scene_wavs(_scenes(1), tmp_path, 0)
    assert isinstance(result, list) and result[0].frames == 999


def test_each_file_read_once(tmp_path, monkeypatch):
    for i in (1, 2, 3):
        _put(tmp_path, i, make_wav(10))
    mod = sys.modules["scenevoice.synth.load_scene_wavs"]
    calls = []

    def counting(data):
        calls.append(len(data))
        return read_wav_frames(data)

    monkeypatch.setattr(mod, "read_wav_frames", counting)
    assert isinstance(load_scene_wavs(_scenes(3), tmp_path, 0), list)
    assert len(calls) == 3  # positive control: the patch is live


def test_file_bytes_read_once_from_disk(tmp_path, monkeypatch):
    from pathlib import Path

    for i in (1, 2):
        _put(tmp_path, i, make_wav(10))
    reads = []
    orig = Path.read_bytes

    def counting(self):
        reads.append(self.name)
        return orig(self)

    monkeypatch.setattr(Path, "read_bytes", counting)
    assert isinstance(load_scene_wavs(_scenes(2), tmp_path, 0), list)
    assert reads == ["001.wav", "002.wav"]
