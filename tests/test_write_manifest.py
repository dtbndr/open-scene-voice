import os
import stat

from scenevoice.pack import write_manifest

DATA = b"scene,duration\n001,0:01.000\n"


def _set_umask(value):
    old = os.umask(value)
    return old


def test_success_writes_exact_bytes_and_nothing_else(tmp_path):
    assert write_manifest(tmp_path, DATA) is None
    assert os.listdir(tmp_path) == ["scene_manifest.csv"]
    assert (tmp_path / "scene_manifest.csv").read_bytes() == DATA


def test_mode_is_umask_derived_not_0600(tmp_path):
    old = _set_umask(0o027)
    try:
        assert write_manifest(tmp_path, DATA) is None
    finally:
        os.umask(old)
    mode = stat.S_IMODE(os.stat(tmp_path / "scene_manifest.csv").st_mode)
    assert mode == 0o640


def test_failure_at_rename_leaves_nothing(tmp_path, monkeypatch):
    calls = []

    def fake(*args, **kwargs):
        calls.append(args)
        raise OSError("injected")

    monkeypatch.setattr(os, "replace", fake)
    message = write_manifest(tmp_path, DATA)
    assert calls, "positive control: fake os.replace was called"
    assert not str(calls[0][0]).endswith(".csv")
    assert isinstance(message, str) and "scene_manifest.csv" in message
    assert "\n" not in message
    assert os.listdir(tmp_path) == []


def test_failure_at_temp_write_leaves_nothing(tmp_path, monkeypatch):
    calls = []

    def fake_fdopen(fd, *args, **kwargs):
        calls.append(fd)
        os.close(fd)
        raise OSError("injected")

    monkeypatch.setattr(os, "fdopen", fake_fdopen)
    message = write_manifest(tmp_path, DATA)
    assert calls, "positive control: fake os.fdopen was called"
    assert isinstance(message, str) and "scene_manifest.csv" in message
    assert os.listdir(tmp_path) == []


def test_failed_write_leaves_existing_manifest_untouched(tmp_path, monkeypatch):
    existing = tmp_path / "scene_manifest.csv"
    existing.write_bytes(b"old\n")
    calls = []

    def fake(*args, **kwargs):
        calls.append(args)
        raise OSError("injected")

    monkeypatch.setattr(os, "replace", fake)
    assert write_manifest(tmp_path, DATA) is not None
    assert calls, "positive control: fake os.replace was called"
    assert existing.read_bytes() == b"old\n"
    assert os.listdir(tmp_path) == ["scene_manifest.csv"]


def test_failure_when_directory_missing_reports_without_raising(tmp_path):
    message = write_manifest(tmp_path / "absent", DATA)
    assert isinstance(message, str) and "scene_manifest.csv" in message
