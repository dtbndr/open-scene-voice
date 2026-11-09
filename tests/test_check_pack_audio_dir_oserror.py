import os
import sys

from scenevoice.pack import check_pack_audio_dir


def test_unexpected_oserror_says_cannot_be_checked(tmp_path, monkeypatch):
    module = sys.modules["scenevoice.pack.check_pack_audio_dir"]
    reached = []

    def boom(path):
        reached.append(path)
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(module.os, "lstat", boom)
    message = check_pack_audio_dir(tmp_path)
    assert reached, "positive control: the patched lstat was reached"
    assert message == f"{tmp_path}/audio: cannot be checked (Permission denied)"


def test_unpatched_lstat_still_works(tmp_path):
    (tmp_path / "audio").mkdir()
    assert os.lstat(tmp_path / "audio")
    assert check_pack_audio_dir(tmp_path) is None
