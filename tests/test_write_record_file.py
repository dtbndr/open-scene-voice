import os
import sys

from scenevoice.synth.write_record_file import write_record_file

DATA = b'{\n  "scenes": []\n}\n'
MESSAGE = "could not write synth_record.json"


def _module():
    return sys.modules["scenevoice.synth.write_record_file"]


def test_creates_file_with_exact_bytes(tmp_path):
    assert write_record_file(tmp_path, DATA) is None
    assert os.listdir(tmp_path) == ["synth_record.json"]
    assert (tmp_path / "synth_record.json").read_bytes() == DATA


def test_replaces_existing_regular_file(tmp_path):
    (tmp_path / "synth_record.json").write_bytes(b"old")
    assert write_record_file(tmp_path, DATA) is None
    assert (tmp_path / "synth_record.json").read_bytes() == DATA
    assert os.listdir(tmp_path) == ["synth_record.json"]


def test_final_file_has_umask_derived_mode(tmp_path):
    old = os.umask(0o022)
    try:
        assert write_record_file(tmp_path, DATA) is None
    finally:
        os.umask(old)
    assert (tmp_path / "synth_record.json").stat().st_mode & 0o777 == 0o644


def test_rename_failure_keeps_old_file_and_leaves_no_temp(tmp_path, monkeypatch):
    target = tmp_path / "synth_record.json"
    target.write_bytes(b"old")
    calls = []

    def fake_replace(src, dst):
        calls.append(src)
        raise OSError("boom")

    monkeypatch.setattr(_module().os, "replace", fake_replace)
    assert write_record_file(tmp_path, DATA) == MESSAGE
    assert calls  # positive control: the fake was reached
    assert target.read_bytes() == b"old"
    assert os.listdir(tmp_path) == ["synth_record.json"]


def test_write_failure_after_temp_created_leaves_no_temp(tmp_path, monkeypatch):
    calls = []

    def fake_chmod(path, mode):
        calls.append(path)
        raise OSError("boom")

    monkeypatch.setattr(_module().os, "chmod", fake_chmod)
    assert write_record_file(tmp_path, DATA) == MESSAGE
    assert calls
    assert os.listdir(tmp_path) == []


def test_temp_name_never_ends_json(tmp_path, monkeypatch):
    seen = []

    def fake_replace(src, dst):
        seen.append(os.path.basename(src))
        raise OSError("boom")

    def fake_remove(path):
        raise OSError("boom")

    monkeypatch.setattr(_module().os, "replace", fake_replace)
    monkeypatch.setattr(_module().os, "remove", fake_remove)
    assert write_record_file(tmp_path, DATA) == MESSAGE
    leftovers = os.listdir(tmp_path)
    monkeypatch.undo()
    assert seen and len(leftovers) == 1
    assert not any(n.endswith(".json") for n in seen + leftovers)


def test_missing_directory_returns_message_not_raises(tmp_path):
    assert write_record_file(tmp_path / "absent", DATA) == MESSAGE
