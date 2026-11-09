from scenevoice.synth import check_audio_dir_full
from scenevoice.validation import Violation

MESSAGE = "--out/audio exists and is not a real directory"


def test_missing_path_passes(tmp_path):
    assert check_audio_dir_full(tmp_path) is None


def test_missing_out_dir_passes(tmp_path):
    assert check_audio_dir_full(tmp_path / "nope") is None


def test_real_directory_passes(tmp_path):
    (tmp_path / "audio").mkdir()
    assert check_audio_dir_full(tmp_path) is None


def test_regular_file_refused(tmp_path):
    (tmp_path / "audio").write_bytes(b"x")
    result = check_audio_dir_full(tmp_path)
    assert isinstance(result, Violation)
    assert result.message == MESSAGE


def test_symlink_to_directory_refused(tmp_path):
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "audio").symlink_to(tmp_path / "elsewhere")
    result = check_audio_dir_full(tmp_path)
    assert isinstance(result, Violation)
    assert result.message == MESSAGE


def test_dangling_symlink_refused(tmp_path):
    (tmp_path / "audio").symlink_to(tmp_path / "missing")
    result = check_audio_dir_full(tmp_path)
    assert isinstance(result, Violation)
    assert result.message == MESSAGE
