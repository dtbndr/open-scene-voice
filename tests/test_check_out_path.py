import os

from scenevoice.synth.check_out_path import check_out_path
from scenevoice.validation import Violation


def test_nonexistent_path_passes_and_is_not_created(tmp_path):
    path = tmp_path / "a" / "b"
    assert check_out_path(path) is None
    assert not os.path.lexists(tmp_path / "a")


def test_existing_directory_passes(tmp_path):
    assert check_out_path(tmp_path) is None


def test_symlink_to_directory_passes(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    assert check_out_path(link) is None


def test_dangling_symlink_passes_at_this_step(tmp_path):
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "missing")
    assert check_out_path(link) is None


def test_regular_file_fails(tmp_path):
    f = tmp_path / "file"
    f.write_bytes(b"x")
    result = check_out_path(f)
    assert isinstance(result, Violation)
    assert f.read_bytes() == b"x"


def test_symlink_to_regular_file_fails(tmp_path):
    f = tmp_path / "file"
    f.write_bytes(b"x")
    link = tmp_path / "link"
    link.symlink_to(f)
    assert isinstance(check_out_path(link), Violation)


def test_accepts_str_path(tmp_path):
    assert check_out_path(str(tmp_path)) is None


def test_creates_nothing_in_any_case(tmp_path):
    f = tmp_path / "file"
    f.write_bytes(b"x")
    before = sorted(os.listdir(tmp_path))
    check_out_path(f)
    check_out_path(tmp_path / "new")
    assert sorted(os.listdir(tmp_path)) == before
