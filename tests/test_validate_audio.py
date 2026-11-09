import io
import struct
import wave

import pytest

from scenevoice.synth.provider import ProviderAudio
from scenevoice.synth.validate_audio import validate_audio
from scenevoice.validation import Violation

GOOD_MIME = "audio/wav"


def make_wav(rate=24000, channels=1, width=2, frames=10):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setframerate(rate)
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.writeframes(bytes(frames * channels * width))
    return buf.getvalue()


def declare_frames(wav, declared):
    """Rewrite the data chunk size so the header declares `declared` bytes of frames."""
    data_at = wav.index(b"data") + 4
    return wav[:data_at] + struct.pack("<I", declared) + wav[data_at + 4 :]


def check(mime, wav):
    return validate_audio(ProviderAudio(mime, wav))


def assert_rejected(result):
    assert isinstance(result, Violation)
    assert result.rule == "synth-response"
    assert result.message.startswith("provider response rejected")
    assert "\n" not in result.message and "\r" not in result.message


def test_accepts_valid_wav():
    assert check(GOOD_MIME, make_wav()) is None


@pytest.mark.parametrize("mime", ["AUDIO/WAV", "audio/wav; codec=pcm", " audio/wav ", "Audio/Wav;x=1"])
def test_accepts_media_type_case_insensitive_params_ignored(mime):
    assert check(mime, make_wav()) is None


@pytest.mark.parametrize(
    "mime", ["audio/L16;rate=24000", "audio/mpeg", "audio/x-wav", "audio/wave", "", None, 24000, b"audio/wav"]
)
def test_rejects_wrong_media_type(mime):
    assert_rejected(check(mime, make_wav()))


def test_wrong_media_type_message_form():
    result = check("audio/mpeg", make_wav())
    assert result.message == "provider response rejected: media type must be audio/wav (got audio/mpeg)"


def test_media_type_echo_is_bounded():
    result = check("audio/" + "x" * 5000, make_wav())
    assert_rejected(result)
    assert result.message.endswith("(got audio/" + "x" * 34 + "...)")


def test_media_type_echo_replaces_unsafe_characters_exactly():
    result = check("audio/\u00e9\u4e2d\u6587", make_wav())
    assert result.message == "provider response rejected: media type must be audio/wav (got audio/???)"


@pytest.mark.parametrize(
    "mime", ["audio/mp\neg", "audio/mp\r\neg\x00\x07", "audio/é中文", "\x1b[31mred", "a b"]
)
def test_media_type_echo_is_one_line_and_safe(mime):
    result = check(mime, make_wav())
    assert_rejected(result)
    assert result.message.isascii() and result.message.isprintable()
    assert len(result.message.splitlines()) == 1


@pytest.mark.parametrize(
    "wav",
    [
        make_wav(rate=16000),
        make_wav(rate=48000),
        make_wav(channels=2),
        make_wav(width=1),
        make_wav(width=3),
        make_wav(frames=0),
    ],
    ids=["16k", "48k", "stereo", "8bit", "24bit", "zero-frames"],
)
def test_rejects_wrong_header(wav):
    assert_rejected(check(GOOD_MIME, wav))


@pytest.mark.parametrize(
    "wav",
    [make_wav()[:20], b"\x00" * 64, b"RIFF" + b"\xff" * 40, b"", None, "RIFFWAVE", 12345],
    ids=["truncated-header", "garbage", "riff-garbage", "empty", "none", "str", "int"],
)
def test_rejects_unreadable_wav_without_raising(wav):
    assert_rejected(check(GOOD_MIME, wav))


def test_rejects_truncated_body():
    wav = make_wav(frames=10)
    assert_rejected(check(GOOD_MIME, wav[:-6]))


def test_rejects_header_declaring_more_frames_than_present():
    wav = make_wav(frames=10)
    assert_rejected(check(GOOD_MIME, declare_frames(wav, 40)))


def test_accepts_bytearray_body():
    assert check(GOOD_MIME, bytearray(make_wav())) is None


CORRUPT_FMT_SIZE = (
    b"RIFF,\x00\x00\x00WAVEfmt \x10\x00\x00\x16\x01\x00\x01\x00\xc0]\x00\x00\x80\xbb\x0f\x00"
    b"\x02\x00\x10\x00data\x08\x00\x00\x00\x00"
)


def test_rejects_corrupted_fmt_chunk_size_without_raising():
    assert_rejected(check(GOOD_MIME, CORRUPT_FMT_SIZE))


def test_rejects_corrupted_data_chunk_size_without_raising():
    wav = make_wav()
    assert_rejected(check(GOOD_MIME, declare_frames(wav, 0xFFFFFFFF)))
    assert_rejected(check(GOOD_MIME, wav.replace(b"fmt ", b"fmt ", 1)[:12] + b"fmt \xff\xff\xff\xff" + wav[20:]))
