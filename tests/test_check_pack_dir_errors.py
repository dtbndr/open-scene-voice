import errno
import os
import sys

import pytest

from scenevoice.pack import check_pack_dir


def _patch_stat(monkeypatch, error):
    calls = []
    real = os.stat

    def fake(path, *a, **k):
        if str(path).endswith("guarded"):
            calls.append(path)
            raise error
        return real(path, *a, **k)

    monkeypatch.setattr(os, "stat", fake)
    return calls


def test_permission_error_becomes_one_line_message(tmp_path, monkeypatch):
    calls = _patch_stat(monkeypatch, PermissionError(errno.EACCES, "Permission denied"))
    message = check_pack_dir(tmp_path / "guarded")
    assert calls, "the fake os.stat never ran"
    assert isinstance(message, str)
    assert "\n" not in message and "\r" not in message


def test_other_os_error_becomes_message(tmp_path, monkeypatch):
    calls = _patch_stat(monkeypatch, OSError(errno.EIO, "Input/output error"))
    assert isinstance(check_pack_dir(tmp_path / "guarded"), str)
    assert calls


def test_not_a_directory_component_is_a_message(tmp_path):
    f = tmp_path / "f"
    f.write_bytes(b"x")
    assert isinstance(check_pack_dir(f / "child"), str)


def test_dangling_symlink_is_a_message(tmp_path):
    link = tmp_path / "dangling"
    try:
        link.symlink_to(tmp_path / "missing")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported")
    assert isinstance(check_pack_dir(link), str)


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="needs POSIX non-root")
def test_directory_under_unsearchable_parent_does_not_raise(tmp_path):
    parent = tmp_path / "locked"
    (parent / "inner").mkdir(parents=True)
    parent.chmod(0)
    try:
        assert isinstance(check_pack_dir(parent / "inner"), str)
    finally:
        parent.chmod(0o700)
