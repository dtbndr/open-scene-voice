import os
import sys

import pytest

from scenevoice.synth.check_scene_target import check_scene_target
from scenevoice.validation import Violation


@pytest.fixture(autouse=True)
def _audio_dir(tmp_path):
    (tmp_path / "audio").mkdir()


def test_absent_target_passes(tmp_path):
    assert check_scene_target(tmp_path, 4) is None


def test_existing_regular_file_passes(tmp_path):
    (tmp_path / "audio" / "004.wav").write_bytes(b"x")
    assert check_scene_target(tmp_path, 4) is None


def test_directory_target_is_refused(tmp_path):
    (tmp_path / "audio" / "004.wav").mkdir()
    violation = check_scene_target(tmp_path, 4)
    assert isinstance(violation, Violation)
    assert violation.rule == "scene-target"
    assert violation.message == "004.wav exists and is not a regular file"


def test_symlink_to_regular_file_is_refused(tmp_path):
    real = tmp_path / "audio" / "real.wav"
    real.write_bytes(b"x")
    (tmp_path / "audio" / "004.wav").symlink_to(real)
    violation = check_scene_target(tmp_path, 4)
    assert violation is not None
    assert violation.message == "004.wav exists and is not a regular file"


def test_dangling_symlink_is_refused(tmp_path):
    (tmp_path / "audio" / "004.wav").symlink_to(tmp_path / "audio" / "nowhere")
    violation = check_scene_target(tmp_path, 4)
    assert violation is not None
    assert violation.message == "004.wav exists and is not a regular file"


def test_other_scenes_files_are_ignored(tmp_path):
    (tmp_path / "audio" / "002.wav").mkdir()
    (tmp_path / "audio" / "003.wav").symlink_to(tmp_path / "audio" / "nowhere")
    assert check_scene_target(tmp_path, 4) is None


def test_message_uses_zero_padded_name_of_selected_scene(tmp_path):
    (tmp_path / "audio" / "012.wav").mkdir()
    violation = check_scene_target(tmp_path, 12)
    assert violation is not None
    assert violation.message == "012.wav exists and is not a regular file"


def test_unsearchable_directory_is_a_violation(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root ignores directory permissions")
    (tmp_path / "audio").chmod(0)
    try:
        violation = check_scene_target(tmp_path, 4)
    finally:
        (tmp_path / "audio").chmod(0o755)
    assert violation is not None
    assert violation.rule == "scene-target"
    assert violation.message == "could not check 004.wav"


def test_lstat_oserror_is_a_violation(tmp_path, monkeypatch):
    reached = []
    module = sys.modules["scenevoice.synth.check_scene_target"]

    def boom(path):
        reached.append(path)
        raise OSError("nope")

    monkeypatch.setattr(module.os, "lstat", boom)
    violation = check_scene_target(tmp_path, 12)
    assert reached, "positive control: the patched lstat was reached"
    assert violation is not None
    assert violation.message == "could not check 012.wav"
