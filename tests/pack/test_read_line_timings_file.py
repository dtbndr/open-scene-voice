import os
import sys

from scenevoice.pack import read_line_timings_file


def test_absent_is_none(tmp_path):
    assert read_line_timings_file(tmp_path) is None


def test_directory_missing_is_none(tmp_path):
    assert read_line_timings_file(tmp_path / "nope") is None


def test_parent_is_a_file_is_none(tmp_path):
    (tmp_path / "f").write_bytes(b"x")
    assert read_line_timings_file(tmp_path / "f") is None


def test_regular_file_returns_bytes(tmp_path):
    (tmp_path / "line_timings.json").write_bytes(b"\x00bytes")
    assert read_line_timings_file(tmp_path) == b"\x00bytes"


def test_directory_is_a_message(tmp_path):
    (tmp_path / "line_timings.json").mkdir()
    result = read_line_timings_file(tmp_path)
    assert isinstance(result, str) and "line_timings.json" in result


def test_symlink_is_a_message(tmp_path):
    (tmp_path / "real").write_bytes(b"{}")
    os.symlink(tmp_path / "real", tmp_path / "line_timings.json")
    result = read_line_timings_file(tmp_path)
    assert isinstance(result, str) and "line_timings.json" in result


def test_dangling_symlink_is_a_message_not_absent(tmp_path):
    os.symlink(tmp_path / "gone", tmp_path / "line_timings.json")
    result = read_line_timings_file(tmp_path)
    assert isinstance(result, str) and "line_timings.json" in result


def test_fifo_is_a_message(tmp_path):
    os.mkfifo(tmp_path / "line_timings.json")
    result = read_line_timings_file(tmp_path)
    assert isinstance(result, str) and "not a regular file" in result


def test_lstat_oserror_is_a_message(tmp_path, monkeypatch):
    module = sys.modules["scenevoice.pack.read_line_timings_file"]
    reached = []

    def boom(path):
        reached.append(path)
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(module.os, "lstat", boom)
    result = read_line_timings_file(tmp_path)
    assert reached, "positive control: patched lstat reached"
    assert isinstance(result, str) and "line_timings.json" in result


def test_unreadable_file_is_a_message(tmp_path, monkeypatch):
    (tmp_path / "line_timings.json").write_bytes(b"{}")
    module = sys.modules["scenevoice.pack.read_line_timings_file"]
    reached = []

    def boom(self):
        reached.append(self)
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(module.Path, "read_bytes", boom)
    result = read_line_timings_file(tmp_path)
    assert reached, "positive control: patched read reached"
    assert isinstance(result, str) and "line_timings.json" in result
    assert "Permission denied" in result
