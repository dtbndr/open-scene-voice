import os
import sys

from scenevoice.synth import check_audio_dir_scene
from scenevoice.validation import Violation

MESSAGE = "--out/audio does not exist or is not a directory"


def test_real_directory_passes(tmp_path):
    (tmp_path / "audio").mkdir()
    assert check_audio_dir_scene(tmp_path) is None


def test_missing_audio_is_refused_and_nothing_created(tmp_path):
    violation = check_audio_dir_scene(tmp_path)
    assert isinstance(violation, Violation)
    assert violation.message == MESSAGE
    assert list(tmp_path.iterdir()) == []


def test_regular_file_is_refused(tmp_path):
    (tmp_path / "audio").write_bytes(b"x")
    violation = check_audio_dir_scene(tmp_path)
    assert violation is not None and violation.message == MESSAGE


def test_symlink_to_directory_is_refused(tmp_path):
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "audio").symlink_to(tmp_path / "elsewhere")
    violation = check_audio_dir_scene(tmp_path)
    assert violation is not None and violation.message == MESSAGE


def test_dangling_symlink_is_refused(tmp_path):
    (tmp_path / "audio").symlink_to(tmp_path / "nowhere")
    violation = check_audio_dir_scene(tmp_path)
    assert violation is not None and violation.message == MESSAGE


def test_lstat_is_used_and_reached(tmp_path, monkeypatch):
    reached = []
    module = sys.modules["scenevoice.synth.check_audio_dir_scene"]
    real = os.lstat

    def spy(path):
        reached.append(path)
        return real(path)

    monkeypatch.setattr(module.os, "lstat", spy)
    (tmp_path / "audio").mkdir()
    assert check_audio_dir_scene(tmp_path) is None
    assert reached, "positive control: the patched lstat was reached"
