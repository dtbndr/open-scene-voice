import errno
import os

import pytest

from scenevoice.pack import check_pack_dir


def _symlink(link, target, is_dir=False):
    try:
        link.symlink_to(target, target_is_directory=is_dir)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported")


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


def test_existing_directory_passes(tmp_path):
    assert check_pack_dir(tmp_path) is None


def test_symlink_to_directory_passes(tmp_path):
    (tmp_path / "real").mkdir()
    _symlink(tmp_path / "link", tmp_path / "real", True)
    assert check_pack_dir(tmp_path / "link") is None


@pytest.mark.parametrize("kind", ["missing", "regular-file", "not-a-directory-component", "dangling-symlink"])
def test_problem_paths_give_a_message(tmp_path, kind):
    (tmp_path / "f").write_bytes(b"x")
    _symlink(tmp_path / "dangling", tmp_path / "missing")
    path = {
        "missing": tmp_path / "nope",
        "regular-file": tmp_path / "f",
        "not-a-directory-component": tmp_path / "f" / "child",
        "dangling-symlink": tmp_path / "dangling",
    }[kind]
    assert isinstance(check_pack_dir(path), str)


@pytest.mark.parametrize(
    "error",
    [PermissionError(errno.EACCES, "Permission denied"), OSError(errno.EIO, "Input/output error")],
    ids=["permission", "io"],
)
def test_os_error_becomes_one_line_message(tmp_path, monkeypatch, error):
    calls = _patch_stat(monkeypatch, error)
    message = check_pack_dir(tmp_path / "guarded")
    assert calls, "the fake os.stat never ran"
    assert isinstance(message, str)
    assert "\n" not in message and "\r" not in message
