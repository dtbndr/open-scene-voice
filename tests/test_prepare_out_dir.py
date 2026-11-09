import os

import pytest

from scenevoice.synth.prepare_out_dir import prepare_out_dir
from scenevoice.validation import Violation


def test_new_nested_path_is_created_with_parents_and_left_clean(tmp_path):
    path = tmp_path / "a" / "b" / "c"
    assert prepare_out_dir(path) is None
    assert path.is_dir()
    assert os.listdir(path) == []


def test_existing_directory_accepted_and_files_left_alone(tmp_path):
    (tmp_path / "007.wav").write_bytes(b"old")
    (tmp_path / "notes.txt").write_bytes(b"n")
    assert prepare_out_dir(tmp_path) is None
    assert sorted(os.listdir(tmp_path)) == ["007.wav", "notes.txt"]
    assert (tmp_path / "007.wav").read_bytes() == b"old"


def test_symlink_to_directory_accepted(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    assert prepare_out_dir(link) is None
    assert os.listdir(real) == []


def test_dangling_symlink_returns_violation(tmp_path):
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "missing")
    assert isinstance(prepare_out_dir(link), Violation)
    assert not (tmp_path / "missing").exists()


def test_regular_file_returns_violation(tmp_path):
    f = tmp_path / "file"
    f.write_bytes(b"x")
    assert isinstance(prepare_out_dir(f), Violation)


def test_path_under_a_regular_file_returns_violation(tmp_path):
    f = tmp_path / "file"
    f.write_bytes(b"x")
    assert isinstance(prepare_out_dir(f / "sub"), Violation)


@pytest.mark.skipif(os.geteuid() == 0, reason="permissions not enforced for root")
def test_read_only_directory_fails_the_probe(tmp_path):
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o555)
    try:
        assert isinstance(prepare_out_dir(ro), Violation)
        assert os.listdir(ro) == []
    finally:
        ro.chmod(0o755)


def test_repeated_calls_leave_no_files(tmp_path):
    for _ in range(3):
        assert prepare_out_dir(tmp_path) is None
    assert os.listdir(tmp_path) == []
