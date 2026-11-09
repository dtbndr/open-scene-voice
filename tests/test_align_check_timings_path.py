import os
import sys

from scenevoice.align import check_timings_path


def test_absent_passes(tmp_path):
    assert check_timings_path(tmp_path) is None


def test_regular_file_passes(tmp_path):
    (tmp_path / "line_timings.json").write_bytes(b"{}")
    assert check_timings_path(tmp_path) is None


def test_directory_fails(tmp_path):
    (tmp_path / "line_timings.json").mkdir()
    message = check_timings_path(tmp_path)
    assert message is not None and "line_timings.json" in message


def test_symlink_to_file_fails(tmp_path):
    (tmp_path / "real.json").write_bytes(b"{}")
    os.symlink(tmp_path / "real.json", tmp_path / "line_timings.json")
    message = check_timings_path(tmp_path)
    assert message is not None and "line_timings.json" in message


def test_symlink_to_directory_fails(tmp_path):
    (tmp_path / "d").mkdir()
    os.symlink(tmp_path / "d", tmp_path / "line_timings.json")
    message = check_timings_path(tmp_path)
    assert message is not None and "line_timings.json" in message


def test_dangling_symlink_fails(tmp_path):
    os.symlink(tmp_path / "nowhere", tmp_path / "line_timings.json")
    message = check_timings_path(tmp_path)
    assert message is not None and "line_timings.json" in message


def test_other_oserror_gives_message_never_raises(tmp_path, monkeypatch):
    module = sys.modules["scenevoice.align.check_timings_path"]
    reached = []

    def boom(path):
        reached.append(path)
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(module.os, "lstat", boom)
    message = check_timings_path(tmp_path)
    assert reached, "positive control: the patched lstat was reached"
    assert message is not None and "line_timings.json" in message
    assert "\n" not in message


def test_not_a_directory_parent_counts_as_absent(tmp_path, monkeypatch):
    module = sys.modules["scenevoice.align.check_timings_path"]
    reached = []

    def gone(path):
        reached.append(path)
        raise NotADirectoryError(20, "Not a directory")

    monkeypatch.setattr(module.os, "lstat", gone)
    assert check_timings_path(tmp_path) is None
    assert reached, "positive control: the patched lstat was reached"
