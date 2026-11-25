import os

import pytest

from scenevoice.synth import (
    check_audio_dir_full,
    check_audio_dir_scene,
    check_record_path,
)
from scenevoice.synth.check_out_dir_exists import check_out_dir_exists
from scenevoice.synth.check_out_path import check_out_path
from scenevoice.synth.find_collisions import find_collisions
from scenevoice.synth.prepare_out_dir import prepare_out_dir
from scenevoice.validation import Violation

_MESSAGE = "--out does not exist or is not a directory"


def test_dir_exists_existing_directory_passes(tmp_path):
    assert check_out_dir_exists(tmp_path) is None


def test_dir_exists_missing_path_is_refused_and_not_created(tmp_path):
    path = tmp_path / "a" / "b"
    violation = check_out_dir_exists(path)
    assert isinstance(violation, Violation)
    assert violation.rule == "out-dir"
    assert violation.message == _MESSAGE
    assert not os.path.lexists(tmp_path / "a")


def test_dir_exists_regular_file_is_refused(tmp_path):
    path = tmp_path / "out"
    path.write_bytes(b"x")
    violation = check_out_dir_exists(path)
    assert violation is not None
    assert violation.message == _MESSAGE


def test_out_path_nonexistent_path_passes_and_is_not_created(tmp_path):
    path = tmp_path / "a" / "b"
    assert check_out_path(path) is None
    assert not os.path.lexists(tmp_path / "a")


def test_out_path_existing_directory_passes(tmp_path):
    assert check_out_path(tmp_path) is None


def test_out_path_regular_file_fails(tmp_path):
    f = tmp_path / "file"
    f.write_bytes(b"x")
    result = check_out_path(f)
    assert isinstance(result, Violation)
    assert result.message == "--out exists and is not a directory"
    assert f.read_bytes() == b"x"


TEXT = "synth_record.json exists and is not a regular file"


def test_record_path_absent_path_passes(tmp_path):
    assert check_record_path(tmp_path) is None


def test_record_path_directory_is_refused(tmp_path):
    (tmp_path / "synth_record.json").mkdir()
    violation = check_record_path(tmp_path)
    assert violation is not None and violation.message == TEXT


def test_record_path_symlink_to_regular_file_is_refused(tmp_path):
    (tmp_path / "real.json").write_bytes(b"{}")
    os.symlink(tmp_path / "real.json", tmp_path / "synth_record.json")
    violation = check_record_path(tmp_path)
    assert violation is not None and violation.message == TEXT


def test_record_path_dangling_symlink_is_refused(tmp_path):
    os.symlink(tmp_path / "nowhere", tmp_path / "synth_record.json")
    violation = check_record_path(tmp_path)
    assert violation is not None and violation.message == TEXT


def test_prepare_new_nested_path_is_created_with_parents_and_left_clean(tmp_path):
    path = tmp_path / "a" / "b" / "c"
    assert prepare_out_dir(path) is None
    assert path.is_dir()
    assert os.listdir(path) == []


def test_prepare_existing_directory_accepted_and_files_left_alone(tmp_path):
    (tmp_path / "007.wav").write_bytes(b"old")
    (tmp_path / "notes.txt").write_bytes(b"n")
    assert prepare_out_dir(tmp_path) is None
    assert sorted(os.listdir(tmp_path)) == ["007.wav", "notes.txt"]
    assert (tmp_path / "007.wav").read_bytes() == b"old"


def test_prepare_dangling_symlink_returns_violation(tmp_path):
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "missing")
    assert isinstance(prepare_out_dir(link), Violation)
    assert not (tmp_path / "missing").exists()


def test_prepare_regular_file_returns_violation(tmp_path):
    f = tmp_path / "file"
    f.write_bytes(b"x")
    assert isinstance(prepare_out_dir(f), Violation)


@pytest.mark.skipif(os.geteuid() == 0, reason="permissions not enforced for root")
def test_prepare_read_only_directory_fails_the_probe(tmp_path):
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o555)
    try:
        assert isinstance(prepare_out_dir(ro), Violation)
        assert os.listdir(ro) == []
    finally:
        ro.chmod(0o755)


FULL = "--out/audio exists and is not a real directory"


SCENE = "--out/audio does not exist or is not a directory"


def _regular_file(tmp_path):
    (tmp_path / "audio").write_bytes(b"x")


def _symlink_to_directory(tmp_path):
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "audio").symlink_to(tmp_path / "elsewhere")


def _dangling_symlink(tmp_path):
    (tmp_path / "audio").symlink_to(tmp_path / "missing")


NOT_A_REAL_DIRECTORY = pytest.mark.parametrize(
    "make", [_regular_file, _symlink_to_directory, _dangling_symlink], ids=["file", "symlink", "dangling"]
)


def test_audio_dir_full_real_directory_passes(tmp_path):
    (tmp_path / "audio").mkdir()
    assert check_audio_dir_full(tmp_path) is None


def test_audio_dir_full_missing_audio_passes(tmp_path):
    assert check_audio_dir_full(tmp_path) is None


@NOT_A_REAL_DIRECTORY
def test_audio_dir_full_refuses_anything_but_a_real_directory(tmp_path, make):
    make(tmp_path)
    result = check_audio_dir_full(tmp_path)
    assert isinstance(result, Violation)
    assert result.message == FULL


def test_audio_dir_scene_missing_audio_is_refused_and_nothing_created(tmp_path):
    violation = check_audio_dir_scene(tmp_path)
    assert isinstance(violation, Violation)
    assert violation.message == SCENE
    assert list(tmp_path.iterdir()) == []


@NOT_A_REAL_DIRECTORY
# Security criterion 2 (outside the project): a symlinked audio folder is refused.
def test_audio_dir_scene_refuses_anything_but_a_real_directory(tmp_path, make):
    make(tmp_path)
    violation = check_audio_dir_scene(tmp_path)
    assert violation is not None and violation.message == SCENE


def audio_dir(tmp_path):
    path = tmp_path / "audio"
    path.mkdir()
    return path


def test_missing_directory_has_no_collisions_and_is_not_created(tmp_path):
    out = tmp_path / "nope"
    assert find_collisions(out, [1, 2, 3]) == []
    assert not os.path.lexists(out)


def test_existing_file_collides(tmp_path):
    (audio_dir(tmp_path) / "002.wav").write_bytes(b"x")
    assert find_collisions(tmp_path, [1, 2, 3]) == [2]


# P0 (paid audio): a dangling symlink at a WAV name is a collision, never written through.
def test_dangling_symlink_collides(tmp_path):
    (audio_dir(tmp_path) / "001.wav").symlink_to(tmp_path / "missing")
    assert find_collisions(tmp_path, [1, 2]) == [1]


def test_stale_longer_plan_file_and_unrelated_files_do_not_collide(tmp_path):
    audio = audio_dir(tmp_path)
    (audio / "007.wav").write_bytes(b"x")
    (audio / "notes.txt").write_bytes(b"x")
    (audio / "1.wav").write_bytes(b"x")
    assert find_collisions(tmp_path, [1, 2, 3]) == []


def test_multiple_collisions_reported_in_ordinal_order(tmp_path):
    audio = audio_dir(tmp_path)
    for name in ("003.wav", "001.wav"):
        (audio / name).write_bytes(b"x")
    assert find_collisions(tmp_path, [1, 2, 3]) == [1, 3]
