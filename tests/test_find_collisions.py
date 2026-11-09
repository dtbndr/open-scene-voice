import os

from scenevoice.synth.find_collisions import find_collisions


def audio_dir(tmp_path):
    path = tmp_path / "audio"
    path.mkdir()
    return path


def test_missing_directory_has_no_collisions_and_is_not_created(tmp_path):
    out = tmp_path / "nope"
    assert find_collisions(out, [1, 2, 3]) == []
    assert not os.path.lexists(out)


def test_empty_directory_has_no_collisions(tmp_path):
    audio_dir(tmp_path)
    assert find_collisions(tmp_path, [1, 2]) == []


def test_existing_file_collides(tmp_path):
    (audio_dir(tmp_path) / "002.wav").write_bytes(b"x")
    assert find_collisions(tmp_path, [1, 2, 3]) == [2]


def test_directory_named_like_wav_collides(tmp_path):
    (audio_dir(tmp_path) / "001.wav").mkdir()
    assert find_collisions(tmp_path, [1, 2]) == [1]


def test_symlink_to_file_collides(tmp_path):
    target = tmp_path / "real.txt"
    target.write_bytes(b"x")
    (audio_dir(tmp_path) / "003.wav").symlink_to(target)
    assert find_collisions(tmp_path, [1, 2, 3]) == [3]


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


def test_accepts_str_path(tmp_path):
    (audio_dir(tmp_path) / "001.wav").write_bytes(b"x")
    assert find_collisions(str(tmp_path), [1]) == [1]


def test_no_ordinals_gives_no_collisions(tmp_path):
    (audio_dir(tmp_path) / "001.wav").write_bytes(b"x")
    assert find_collisions(tmp_path, []) == []
