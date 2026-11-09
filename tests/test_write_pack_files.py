import os
import stat
import sys

from scenevoice.pack import write_pack_files

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


def test_first_rename_failure_leaves_nothing_and_keeps_existing(tmp_path, monkeypatch):
    (tmp_path / "keep.txt").write_text("x")
    calls = []

    def fake(src, dst):
        calls.append(dst)
        raise OSError("injected")

    monkeypatch.setattr(os, "replace", fake)
    message = write_pack_files(tmp_path, MANIFEST, TIMELINE)
    assert calls, "positive control: fake os.replace was called"
    assert os.listdir(tmp_path) == ["keep.txt"]
    assert message == "could not write scene_manifest.csv"


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


def test_rollback_never_touches_preexisting_files(tmp_path, monkeypatch):
    # An older scene_manifest.csv exists (caller's collision check is earlier);
    # a failure at the FIRST rename must not remove it.
    (tmp_path / "scene_manifest.csv").write_bytes(b"old")

    def fake(src, dst):
        raise OSError("injected")

    monkeypatch.setattr(os, "replace", fake)
    write_pack_files(tmp_path, MANIFEST, TIMELINE)
    assert (tmp_path / "scene_manifest.csv").read_bytes() == b"old"
    assert os.listdir(tmp_path) == ["scene_manifest.csv"]


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
