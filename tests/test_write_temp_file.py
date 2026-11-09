import os
import stat
import sys

import pytest

from scenevoice.pack import write_temp_file

DATA = b"abc\n"


def test_writes_bytes_to_temp_name_not_csv_or_otio(tmp_path):
    path = write_temp_file(tmp_path, DATA)
    name = os.path.basename(path)
    assert os.listdir(tmp_path) == [name]
    assert name.startswith(".write-") and name.endswith(".tmp")
    assert open(path, "rb").read() == DATA


def test_mode_is_umask_derived_not_0600(tmp_path):
    old = os.umask(0o027)
    try:
        path = write_temp_file(tmp_path, DATA)
    finally:
        os.umask(old)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o640


def test_failure_removes_own_temp_and_raises(tmp_path, monkeypatch):
    calls = []

    def fake(*args, **kwargs):
        calls.append(args)
        raise OSError("injected")

    module = sys.modules["scenevoice.pack.write_temp_file"]
    monkeypatch.setattr(module.os, "chmod", fake)
    with pytest.raises(OSError):
        write_temp_file(tmp_path, DATA)
    assert calls, "positive control: fake chmod was called"
    assert os.listdir(tmp_path) == []
