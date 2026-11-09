import io
import os
import sys
import wave

import pytest

from scenevoice.synth.write_wav import write_wav
from scenevoice.validation import Violation


def _build_wav(frames=2400):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(bytes(frames * 2))
    return buf.getvalue()


WAV = _build_wav()


def _module():
    return sys.modules["scenevoice.synth.write_wav"]


def test_written_bytes_equal_input_wav_exactly(tmp_path):
    assert write_wav(tmp_path, 9, WAV) is None
    assert os.listdir(tmp_path) == ["009.wav"]
    assert (tmp_path / "009.wav").read_bytes() == WAV


def test_success_leaves_only_a_readable_wav(tmp_path):
    assert write_wav(tmp_path, 7, WAV) is None
    assert os.listdir(tmp_path) == ["007.wav"]
    with wave.open(str(tmp_path / "007.wav")) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 24000)
        assert w.getnframes() == 2400


def test_overwrites_existing_file_atomically(tmp_path):
    (tmp_path / "001.wav").write_bytes(b"old")
    assert write_wav(tmp_path, 1, WAV) is None
    assert os.listdir(tmp_path) == ["001.wav"]
    with wave.open(str(tmp_path / "001.wav")) as w:
        assert w.getnframes() == 2400


def test_other_files_untouched(tmp_path):
    (tmp_path / "notes.txt").write_bytes(b"n")
    assert write_wav(tmp_path, 2, WAV) is None
    assert sorted(os.listdir(tmp_path)) == ["002.wav", "notes.txt"]


def test_write_failure_returns_violation_and_leaves_no_wav(tmp_path, monkeypatch):
    calls = []

    def fake_mkstemp(*args, **kwargs):
        calls.append(kwargs)
        raise OSError("disk full")

    monkeypatch.setattr(_module().tempfile, "mkstemp", fake_mkstemp)
    result = write_wav(tmp_path, 3, WAV)
    assert len(calls) == 1  # positive control: the patch was hit
    assert result == Violation("out-dir", "could not write 003.wav")
    assert not (tmp_path / "003.wav").exists()
    assert [n for n in os.listdir(tmp_path) if n.endswith(".wav")] == []


def test_rename_failure_returns_violation_and_cleans_up(tmp_path, monkeypatch):
    calls = []

    def fake_replace(src, dst):
        calls.append((src, dst))
        raise OSError("rename failed")

    monkeypatch.setattr(_module().os, "replace", fake_replace)
    result = write_wav(tmp_path, 4, WAV)
    assert len(calls) == 1  # positive control: the rename was reached
    assert isinstance(result, Violation)
    assert [n for n in os.listdir(tmp_path) if n.endswith(".wav")] == []
    assert os.listdir(tmp_path) == []


def test_unwritable_directory_returns_violation(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("permissions not enforced for root")
    d = tmp_path / "ro"
    d.mkdir()
    d.chmod(0o500)
    try:
        result = write_wav(d, 5, WAV)
        assert isinstance(result, Violation)
        assert os.listdir(d) == []
    finally:
        d.chmod(0o700)


def _mode_under_umask(tmp_path, mask):
    old = os.umask(mask)
    try:
        assert write_wav(tmp_path, 6, WAV) is None
    finally:
        os.umask(old)
    return os.stat(tmp_path / "006.wav").st_mode & 0o777


def test_written_file_has_normal_mode_under_umask_022(tmp_path):
    assert _mode_under_umask(tmp_path, 0o022) == 0o644


def test_written_file_honours_restrictive_umask_077(tmp_path):
    assert _mode_under_umask(tmp_path, 0o077) == 0o600


def test_umask_is_left_unchanged(tmp_path):
    old = os.umask(0o027)
    try:
        assert write_wav(tmp_path, 6, WAV) is None
        assert os.umask(0o027) == 0o027
    finally:
        os.umask(old)


def test_chmod_failure_returns_violation_and_cleans_up(tmp_path, monkeypatch):
    calls = []

    def fake_chmod(path, mode):
        calls.append((path, mode))
        raise OSError("chmod failed")

    monkeypatch.setattr(_module().os, "chmod", fake_chmod)
    result = write_wav(tmp_path, 8, WAV)
    assert len(calls) == 1  # positive control: chmod was reached
    assert isinstance(result, Violation)
    assert [n for n in os.listdir(tmp_path) if n.endswith(".wav")] == []
    assert os.listdir(tmp_path) == []


def test_leftover_temp_name_never_ends_wav(tmp_path, monkeypatch):
    removes = []

    def fake_replace(src, dst):
        raise OSError("rename failed")

    def fake_remove(path):
        removes.append(path)
        raise OSError("remove failed")

    monkeypatch.setattr(_module().os, "replace", fake_replace)
    monkeypatch.setattr(_module().os, "remove", fake_remove)
    result = write_wav(tmp_path, 10, WAV)
    monkeypatch.undo()
    assert len(removes) == 1  # positive control: cleanup was attempted
    assert isinstance(result, Violation)
    leftovers = os.listdir(tmp_path)
    assert len(leftovers) == 1  # the removal failed, so the temp file is left behind
    assert not leftovers[0].endswith(".wav")
