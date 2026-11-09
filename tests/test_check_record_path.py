import os
import stat
import sys

import pytest

from scenevoice.synth import check_record_path

TEXT = "synth_record.json exists and is not a regular file"


def test_absent_path_passes(tmp_path):
    assert check_record_path(tmp_path) is None


def test_missing_directory_passes(tmp_path):
    assert check_record_path(tmp_path / "absent") is None


def test_regular_file_passes(tmp_path):
    (tmp_path / "synth_record.json").write_bytes(b"not json")
    assert check_record_path(tmp_path) is None


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_unreadable_regular_file_passes_without_being_opened(tmp_path):
    path = tmp_path / "synth_record.json"
    path.write_bytes(b"x")
    path.chmod(0)
    try:
        assert check_record_path(tmp_path) is None
    finally:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def test_directory_is_refused(tmp_path):
    (tmp_path / "synth_record.json").mkdir()
    violation = check_record_path(tmp_path)
    assert violation is not None and violation.message == TEXT


def test_symlink_to_regular_file_is_refused(tmp_path):
    (tmp_path / "real.json").write_bytes(b"{}")
    os.symlink(tmp_path / "real.json", tmp_path / "synth_record.json")
    violation = check_record_path(tmp_path)
    assert violation is not None and violation.message == TEXT


def test_dangling_symlink_is_refused(tmp_path):
    os.symlink(tmp_path / "nowhere", tmp_path / "synth_record.json")
    violation = check_record_path(tmp_path)
    assert violation is not None and violation.message == TEXT
