import os
import stat
import sys

import pytest

from scenevoice.pack import write_manifest, write_pack_files, write_temp_file

MANIFEST = b"scene,duration\n"
TIMELINE = b'{"OTIO_SCHEMA": "Timeline.1"}\n'
MODULE = "scenevoice.pack.write_pack_files"


def test_success_writes_both_files_only(tmp_path):
    (tmp_path / "keep.txt").write_text("x")
    assert write_pack_files(tmp_path, MANIFEST, TIMELINE) is None
    assert sorted(os.listdir(tmp_path)) == [
        "keep.txt",
        "resolve_timeline.otio",
        "scene_manifest.csv",
    ]
    assert (tmp_path / "scene_manifest.csv").read_bytes() == MANIFEST
    assert (tmp_path / "resolve_timeline.otio").read_bytes() == TIMELINE


def test_modes_are_umask_derived(tmp_path):
    old = os.umask(0o027)
    try:
        assert write_pack_files(tmp_path, MANIFEST, TIMELINE) is None
    finally:
        os.umask(old)
    for name in ("scene_manifest.csv", "resolve_timeline.otio"):
        assert stat.S_IMODE(os.stat(tmp_path / name).st_mode) == 0o640


def test_second_temp_write_failure_leaves_nothing(tmp_path, monkeypatch):
    module = sys.modules[MODULE]
    real = module.write_temp_file
    calls = []

    def fake(directory, data):
        calls.append(data)
        if len(calls) == 2:
            raise OSError("injected")
        return real(directory, data)

    monkeypatch.setattr(module, "write_temp_file", fake)
    message = write_pack_files(tmp_path, MANIFEST, TIMELINE)
    assert len(calls) == 2, "positive control: fake reached twice"
    assert os.listdir(tmp_path) == []
    assert message == "could not write resolve_timeline.otio"


def test_first_temp_write_failure_names_manifest(tmp_path, monkeypatch):
    module = sys.modules[MODULE]
    calls = []

    def fake(directory, data):
        calls.append(data)
        raise OSError("injected")

    monkeypatch.setattr(module, "write_temp_file", fake)
    message = write_pack_files(tmp_path, MANIFEST, TIMELINE)
    assert calls
    assert message == "could not write scene_manifest.csv"
    assert os.listdir(tmp_path) == []


def test_second_rename_failure_removes_manifest_and_temps(tmp_path, monkeypatch):
    (tmp_path / "keep.txt").write_text("x")
    real = os.replace
    hit = []

    def fake(src, dst):
        if os.path.basename(dst) == "resolve_timeline.otio":
            hit.append(dst)
            raise OSError("injected")
        return real(src, dst)

    monkeypatch.setattr(os, "replace", fake)
    message = write_pack_files(tmp_path, MANIFEST, TIMELINE)
    assert hit, "positive control: timeline rename failed"
    assert os.listdir(tmp_path) == ["keep.txt"]
    assert message == "could not write resolve_timeline.otio"


def test_first_rename_failure_leaves_nothing_and_never_touches_preexisting_files(tmp_path, monkeypatch):
    # An older scene_manifest.csv exists (the caller's collision check is earlier);
    # a failure at the FIRST rename must not remove it, nor any other file.
    (tmp_path / "scene_manifest.csv").write_bytes(b"old")
    (tmp_path / "keep.txt").write_text("x")
    calls = []

    def fake(src, dst):
        calls.append(dst)
        raise OSError("injected")

    monkeypatch.setattr(os, "replace", fake)
    message = write_pack_files(tmp_path, MANIFEST, TIMELINE)
    assert calls, "positive control: fake os.replace was called"
    assert message == "could not write scene_manifest.csv"
    assert (tmp_path / "scene_manifest.csv").read_bytes() == b"old"
    assert sorted(os.listdir(tmp_path)) == ["keep.txt", "scene_manifest.csv"]


def test_temp_names_never_end_csv_or_otio(tmp_path, monkeypatch):
    seen = []
    real = os.replace

    def spy(src, dst):
        seen.append(os.path.basename(src))
        return real(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    assert write_pack_files(tmp_path, MANIFEST, TIMELINE) is None
    assert len(seen) == 2, "positive control: both renames observed"
    for name in seen:
        assert name.startswith(".write-") and name.endswith(".tmp")


def test_cleanup_oserror_is_swallowed(tmp_path, monkeypatch):
    real = os.replace

    def fake(src, dst):
        if os.path.basename(dst) == "resolve_timeline.otio":
            raise OSError("injected")
        return real(src, dst)

    def bad_remove(path):
        raise OSError("cleanup")

    monkeypatch.setattr(os, "replace", fake)
    monkeypatch.setattr(os, "remove", bad_remove)
    message = write_pack_files(tmp_path, MANIFEST, TIMELINE)
    assert message == "could not write resolve_timeline.otio"


# write_manifest

DATA = b"scene,duration\n001,0:01.000\n"


def test_manifest_success_writes_exact_bytes_and_nothing_else(tmp_path):
    assert write_manifest(tmp_path, DATA) is None
    assert os.listdir(tmp_path) == ["scene_manifest.csv"]
    assert (tmp_path / "scene_manifest.csv").read_bytes() == DATA


def test_manifest_mode_is_umask_derived_not_0600(tmp_path):
    old = os.umask(0o027)
    try:
        assert write_manifest(tmp_path, DATA) is None
    finally:
        os.umask(old)
    assert stat.S_IMODE(os.stat(tmp_path / "scene_manifest.csv").st_mode) == 0o640


def test_manifest_failure_at_rename_leaves_nothing_and_existing_manifest_untouched(tmp_path, monkeypatch):
    existing = tmp_path / "scene_manifest.csv"
    existing.write_bytes(b"old\n")
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
    assert existing.read_bytes() == b"old\n"
    assert os.listdir(tmp_path) == ["scene_manifest.csv"]


def test_manifest_failure_at_temp_write_leaves_nothing(tmp_path, monkeypatch):
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


def test_manifest_missing_directory_reports_without_raising(tmp_path):
    message = write_manifest(tmp_path / "absent", DATA)
    assert isinstance(message, str) and "scene_manifest.csv" in message


# write_temp_file


def test_temp_file_writes_bytes_to_temp_name_not_csv_or_otio(tmp_path):
    path = write_temp_file(tmp_path, b"abc\n")
    name = os.path.basename(path)
    assert os.listdir(tmp_path) == [name]
    assert name.startswith(".write-") and name.endswith(".tmp")
    assert open(path, "rb").read() == b"abc\n"


def test_temp_file_mode_is_umask_derived_not_0600(tmp_path):
    old = os.umask(0o027)
    try:
        path = write_temp_file(tmp_path, b"abc\n")
    finally:
        os.umask(old)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o640


def test_temp_file_failure_removes_own_temp_and_raises(tmp_path, monkeypatch):
    calls = []

    def fake(*args, **kwargs):
        calls.append(args)
        raise OSError("injected")

    module = sys.modules["scenevoice.pack.write_temp_file"]
    monkeypatch.setattr(module.os, "chmod", fake)
    with pytest.raises(OSError):
        write_temp_file(tmp_path, b"abc\n")
    assert calls, "positive control: fake chmod was called"
    assert os.listdir(tmp_path) == []
