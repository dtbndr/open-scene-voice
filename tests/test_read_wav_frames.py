import pytest
from wav_helper import make_wav

from scenevoice.synth import read_wav_frames


def test_valid_wav_returns_frame_count():
    assert read_wav_frames(make_wav(frames=10)) == 10


def test_bytearray_is_accepted():
    assert read_wav_frames(bytearray(make_wav(frames=3))) == 3


def test_extra_bytes_after_declared_frames_still_pass():
    # validate_audio reads only the declared frames, so trailing data is ignored.
    wav = make_wav(frames=4)
    assert read_wav_frames(wav + b"\x00\x00\x00\x00") == 4


@pytest.mark.parametrize(
    ("wav", "reason"),
    [
        (make_wav(rate=16000), "rate must be exactly 24000"),
        (make_wav(rate=48000), "rate must be exactly 24000"),
        (make_wav(channels=2), "audio must be mono"),
        (make_wav(width=1), "audio must be 16-bit"),
        (make_wav(width=3), "audio must be 16-bit"),
        (make_wav(frames=0), "audio is empty"),
        (make_wav(frames=10)[:-6], "audio is truncated"),
        (make_wav()[:20], "audio is not a readable WAV file"),
        (b"\x00" * 64, "audio is not a readable WAV file"),
        (b"", "audio is not a readable WAV file"),
    ],
    ids=["16k", "48k", "stereo", "8bit", "24bit", "zero-frames", "truncated", "short-header", "garbage", "empty"],
)
def test_returns_reason_text(wav, reason):
    assert read_wav_frames(wav) == reason


def test_rate_is_checked_before_channels():
    assert read_wav_frames(make_wav(rate=16000, channels=2)) == "rate must be exactly 24000"


def test_channels_are_checked_before_truncation():
    assert read_wav_frames(make_wav(channels=2)[:-6]) == "audio must be mono"


def test_width_is_checked_before_empty():
    assert read_wav_frames(make_wav(width=1, frames=0)) == "audio must be 16-bit"
