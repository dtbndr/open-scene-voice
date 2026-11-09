import os
import sys

from scenevoice.pack import check_no_timeline_collision

MODULE = "scenevoice.pack.check_no_timeline_collision"


def _assert_refused(tmp_path):
    message = check_no_timeline_collision(tmp_path)
    assert isinstance(message, str)
    assert "resolve_timeline.otio" in message


def test_absent_path_is_clear(tmp_path):
    assert check_no_timeline_collision(tmp_path) is None


def test_regular_file_refused(tmp_path):
    (tmp_path / "resolve_timeline.otio").write_bytes(b"x")
    _assert_refused(tmp_path)


def test_empty_file_refused(tmp_path):
    (tmp_path / "resolve_timeline.otio").write_bytes(b"")
    _assert_refused(tmp_path)


def test_directory_refused(tmp_path):
    (tmp_path / "resolve_timeline.otio").mkdir()
    _assert_refused(tmp_path)


def test_symlink_to_file_refused(tmp_path):
    (tmp_path / "real").write_bytes(b"x")
    os.symlink(tmp_path / "real", tmp_path / "resolve_timeline.otio")
    _assert_refused(tmp_path)


def test_symlink_to_directory_refused(tmp_path):
    (tmp_path / "real").mkdir()
    os.symlink(tmp_path / "real", tmp_path / "resolve_timeline.otio")
    _assert_refused(tmp_path)


def test_dangling_symlink_refused(tmp_path):
    os.symlink(tmp_path / "gone", tmp_path / "resolve_timeline.otio")
    _assert_refused(tmp_path)


def test_other_oserror_gives_message_and_does_not_raise(tmp_path, monkeypatch):
    module = sys.modules[MODULE]
    real = module.os.lstat
    calls = []

    def fake(path, *a, **kw):
        if str(path).endswith("resolve_timeline.otio"):
            calls.append(path)
            raise PermissionError(13, "Permission denied")
        return real(path, *a, **kw)

    monkeypatch.setattr(module.os, "lstat", fake)
    message = check_no_timeline_collision(tmp_path)
    assert calls, "positive control: fake lstat reached"
    assert isinstance(message, str)
    assert "resolve_timeline.otio" in message
