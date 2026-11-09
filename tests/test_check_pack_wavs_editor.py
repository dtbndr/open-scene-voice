from wav_helper import make_wav

from scenevoice.pack import SAMPLE_FRAMES_PER_TIMELINE_FRAME, check_pack_wavs
from scenevoice.synth import PlanScene

MIN = SAMPLE_FRAMES_PER_TIMELINE_FRAME


def _scenes(n):
    return [PlanScene(i, f"T{i}", "b") for i in range(1, n + 1)]


def _put(tmp_path, ordinal, data):
    (tmp_path / "audio").mkdir(exist_ok=True)
    (tmp_path / "audio" / f"{ordinal:03d}.wav").write_bytes(data)


def _assert_names(result, ordinal):
    assert isinstance(result, str)
    assert f"scene {ordinal}" in result
    assert f"audio/{ordinal:03d}.wav" in result


def test_999_frames_fail_with_rule(tmp_path):
    _put(tmp_path, 1, make_wav(MIN - 1))
    _assert_names(check_pack_wavs(_scenes(1), tmp_path, min_frames=MIN), 1)


def test_1000_frames_pass_with_rule(tmp_path):
    _put(tmp_path, 1, make_wav(MIN))
    assert check_pack_wavs(_scenes(1), tmp_path, min_frames=MIN) == [MIN]


def test_999_frames_pass_without_rule(tmp_path):
    _put(tmp_path, 1, make_wav(MIN - 1))
    assert check_pack_wavs(_scenes(1), tmp_path) == [MIN - 1]


def test_short_then_missing_reports_scene_1(tmp_path):
    _put(tmp_path, 1, make_wav(MIN - 1))
    _assert_names(check_pack_wavs(_scenes(2), tmp_path, min_frames=MIN), 1)


def test_missing_then_short_reports_scene_1(tmp_path):
    _put(tmp_path, 2, make_wav(MIN - 1))
    result = check_pack_wavs(_scenes(2), tmp_path, min_frames=MIN)
    _assert_names(result, 1)
    assert "not a regular file" in result


def test_invalid_then_short_reports_existing_message(tmp_path):
    _put(tmp_path, 1, make_wav(0))
    _put(tmp_path, 2, make_wav(MIN - 1))
    with_rule = check_pack_wavs(_scenes(2), tmp_path, min_frames=MIN)
    _assert_names(with_rule, 1)
    assert with_rule == check_pack_wavs(_scenes(2), tmp_path)
