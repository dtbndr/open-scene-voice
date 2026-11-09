import os
import stat
import sys

from scenevoice.align import write_timings_file

DATA = b'{"scenes": []}\n'


def test_success_writes_bytes_and_leaves_no_temp(tmp_path):
    assert write_timings_file(tmp_path, DATA) is None
    assert os.listdir(tmp_path) == ["line_timings.json"]
    assert (tmp_path / "line_timings.json").read_bytes() == DATA


def test_mode_is_umask_derived(tmp_path):
    old = os.umask(0o027)
    try:
        assert write_timings_file(tmp_path, DATA) is None
    finally:
        os.umask(old)
    assert stat.S_IMODE(os.stat(tmp_path / "line_timings.json").st_mode) == 0o640


def test_success_overwrites_existing(tmp_path):
    (tmp_path / "line_timings.json").write_bytes(b"old")
    assert write_timings_file(tmp_path, DATA) is None
    assert (tmp_path / "line_timings.json").read_bytes() == DATA


def test_failure_at_replace_keeps_existing_and_removes_temp(tmp_path, monkeypatch):
    existing = tmp_path / "line_timings.json"
    existing.write_bytes(b"old\n")
    calls = []

    def fake(*args, **kwargs):
        calls.append(args)
        raise OSError("injected")

    monkeypatch.setattr(os, "replace", fake)
    message = write_timings_file(tmp_path, DATA)
    assert calls, "positive control: fake os.replace was called"
    assert not str(calls[0][0]).endswith(".json")
    assert isinstance(message, str) and "line_timings.json" in message
    assert "\n" not in message
    assert existing.read_bytes() == b"old\n"
    assert os.listdir(tmp_path) == ["line_timings.json"]


def test_failure_at_temp_write_keeps_existing(tmp_path, monkeypatch):
    existing = tmp_path / "line_timings.json"
    existing.write_bytes(b"old\n")
    calls = []

    def fake_fdopen(fd, *args, **kwargs):
        calls.append(fd)
        os.close(fd)
        raise OSError("injected")

    monkeypatch.setattr(os, "fdopen", fake_fdopen)
    message = write_timings_file(tmp_path, DATA)
    assert calls, "positive control: fake os.fdopen was called"
    assert isinstance(message, str) and "line_timings.json" in message
    assert existing.read_bytes() == b"old\n"
    assert os.listdir(tmp_path) == ["line_timings.json"]


def test_temp_removal_failure_still_returns_message(tmp_path, monkeypatch):
    module = sys.modules["scenevoice.align.write_timings_file"]
    removed = []

    def no_replace(*args, **kwargs):
        raise OSError("injected")

    def no_remove(path):
        removed.append(path)
        raise OSError("cannot remove")

    monkeypatch.setattr(module.os, "replace", no_replace)
    monkeypatch.setattr(module.os, "remove", no_remove)
    message = write_timings_file(tmp_path, DATA)
    assert removed, "positive control: the patched remove was reached"
    assert isinstance(message, str) and "line_timings.json" in message


def test_missing_directory_reports_without_raising(tmp_path):
    message = write_timings_file(tmp_path / "absent", DATA)
    assert isinstance(message, str) and "line_timings.json" in message
