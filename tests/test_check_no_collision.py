import pytest

from scenevoice.pack import check_no_collision

NAME = "scene_manifest.csv"


def test_empty_directory_passes(tmp_path):
    assert check_no_collision(tmp_path) is None


def test_regular_file_collides(tmp_path):
    (tmp_path / NAME).write_bytes(b"x")
    assert NAME in check_no_collision(tmp_path)


def test_directory_collides(tmp_path):
    (tmp_path / NAME).mkdir()
    assert NAME in check_no_collision(tmp_path)


def test_symlink_to_real_file_collides(tmp_path):
    (tmp_path / "real").write_bytes(b"x")
    try:
        (tmp_path / NAME).symlink_to(tmp_path / "real")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported")
    assert NAME in check_no_collision(tmp_path)


def test_dangling_symlink_collides(tmp_path):
    try:
        (tmp_path / NAME).symlink_to(tmp_path / "missing")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported")
    assert NAME in check_no_collision(tmp_path)
