import pytest

from scenevoice.pack import check_pack_dir


def test_existing_directory_passes(tmp_path):
    assert check_pack_dir(tmp_path) is None


def test_nonexistent_path_fails(tmp_path):
    assert isinstance(check_pack_dir(tmp_path / "nope"), str)


def test_regular_file_fails(tmp_path):
    f = tmp_path / "f"
    f.write_bytes(b"x")
    assert isinstance(check_pack_dir(f), str)


def test_symlink_to_directory_passes(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported")
    assert check_pack_dir(link) is None
