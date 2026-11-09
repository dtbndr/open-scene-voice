import pytest

from scenevoice.pack import check_pack_audio_dir


def _symlink(link, target, is_dir):
    try:
        link.symlink_to(target, target_is_directory=is_dir)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported")


def test_real_audio_directory_passes(tmp_path):
    (tmp_path / "audio").mkdir()
    assert check_pack_audio_dir(tmp_path) is None


def test_missing_audio_says_directory_does_not_exist(tmp_path):
    message = check_pack_audio_dir(tmp_path)
    assert message == f"{tmp_path}/audio: directory does not exist"


def test_regular_file_says_not_a_directory(tmp_path):
    (tmp_path / "audio").write_bytes(b"x")
    assert check_pack_audio_dir(tmp_path) == f"{tmp_path}/audio: not a directory"


def test_symlink_to_directory_is_refused(tmp_path):
    (tmp_path / "real").mkdir()
    _symlink(tmp_path / "audio", tmp_path / "real", True)
    assert check_pack_audio_dir(tmp_path) == f"{tmp_path}/audio: not a directory"


def test_dangling_symlink_is_refused(tmp_path):
    _symlink(tmp_path / "audio", tmp_path / "nowhere", False)
    assert check_pack_audio_dir(tmp_path) == f"{tmp_path}/audio: not a directory"


def test_symlinked_dir_with_real_audio_passes(tmp_path):
    real = tmp_path / "real"
    (real / "audio").mkdir(parents=True)
    link = tmp_path / "link"
    _symlink(link, real, True)
    assert check_pack_audio_dir(link) is None
