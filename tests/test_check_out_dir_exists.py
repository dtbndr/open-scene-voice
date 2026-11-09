import os

from scenevoice.synth.check_out_dir_exists import check_out_dir_exists
from scenevoice.validation import Violation

_MESSAGE = "--out does not exist or is not a directory"


def test_existing_directory_passes(tmp_path):
    assert check_out_dir_exists(tmp_path) is None


def test_symlink_to_directory_passes(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    assert check_out_dir_exists(link) is None


def test_missing_path_is_refused_and_not_created(tmp_path):
    path = tmp_path / "a" / "b"
    violation = check_out_dir_exists(path)
    assert isinstance(violation, Violation)
    assert violation.rule == "out-dir"
    assert violation.message == _MESSAGE
    assert not os.path.lexists(tmp_path / "a")


def test_regular_file_is_refused(tmp_path):
    path = tmp_path / "out"
    path.write_bytes(b"x")
    violation = check_out_dir_exists(path)
    assert violation is not None
    assert violation.message == _MESSAGE


def test_dangling_symlink_is_refused(tmp_path):
    link = tmp_path / "out"
    link.symlink_to(tmp_path / "nowhere")
    violation = check_out_dir_exists(link)
    assert violation is not None
    assert violation.message == _MESSAGE
    assert not (tmp_path / "nowhere").exists()
