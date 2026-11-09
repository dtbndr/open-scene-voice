from scenevoice.synth import find_collisions


def audio(tmp_path):
    d = tmp_path / "audio"
    d.mkdir()
    return d


def test_audio_file_collides(tmp_path):
    (audio(tmp_path) / "002.wav").write_bytes(b"x")
    assert find_collisions(tmp_path, [1, 2, 3]) == [2]


def test_audio_directory_and_dangling_symlink_collide(tmp_path):
    d = audio(tmp_path)
    (d / "001.wav").mkdir()
    (d / "003.wav").symlink_to(tmp_path / "missing")
    assert find_collisions(tmp_path, [1, 2, 3]) == [1, 3]


def test_flat_wav_is_ignored(tmp_path):
    audio(tmp_path)
    (tmp_path / "001.wav").write_bytes(b"x")
    assert find_collisions(tmp_path, [1]) == []


def test_missing_audio_dir_has_no_collisions(tmp_path):
    assert find_collisions(tmp_path, [1]) == []
