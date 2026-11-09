from scenevoice.synth.check_scene_target import check_scene_target


def audio(tmp_path):
    path = tmp_path / "audio"
    path.mkdir()
    return path


def test_target_is_looked_up_under_audio(tmp_path):
    folder = audio(tmp_path)
    (folder / "004.wav").mkdir()
    violation = check_scene_target(tmp_path, 4)
    assert violation is not None
    assert violation.message == "004.wav exists and is not a regular file"


def test_flat_file_or_directory_beside_audio_is_ignored(tmp_path):
    audio(tmp_path)
    (tmp_path / "004.wav").mkdir()
    assert check_scene_target(tmp_path, 4) is None


def test_regular_file_under_audio_passes(tmp_path):
    (audio(tmp_path) / "004.wav").write_bytes(b"x")
    assert check_scene_target(tmp_path, 4) is None
