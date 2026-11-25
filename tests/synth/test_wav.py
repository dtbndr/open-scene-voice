import io
import os
import struct
import sys
import wave

import pytest
from wav_helper import make_wav

from scenevoice.synth import (
    PlanScene,
    SceneWav,
    audio_rel_path,
    load_scene_wavs,
    one_line,
    read_wav_frames,
)
from scenevoice.synth.is_text_blank import is_text_blank
from scenevoice.synth.provider import ProviderAudio
from scenevoice.synth.validate_audio import validate_audio
from scenevoice.synth.wav_name import wav_name
from scenevoice.synth.write_wav import write_wav
from scenevoice.validation import Violation


def test_valid_wav_returns_frame_count():
    assert read_wav_frames(make_wav(frames=10)) == 10


@pytest.mark.parametrize(
    ("wav", "reason"),
    [
        (make_wav(rate=16000), "rate must be exactly 24000"),
        (make_wav(channels=2), "audio must be mono"),
        (make_wav(width=1), "audio must be 16-bit"),
        (make_wav(frames=0), "audio is empty"),
        (make_wav(frames=10)[:-6], "audio is truncated"),
        (b"\x00" * 64, "audio is not a readable WAV file"),
    ],
    ids=["16k", "stereo", "8bit", "zero-frames", "truncated", "garbage"],
)
def test_returns_reason_text(wav, reason):
    assert read_wav_frames(wav) == reason


GOOD_MIME = "audio/wav"


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


def test_accepts_media_type_case_insensitive_params_ignored():
    assert check("Audio/Wav; codec=pcm", make_wav()) is None


@pytest.mark.parametrize("mime", ["audio/L16;rate=24000", "", None])
def test_rejects_wrong_media_type(mime):
    assert_rejected(check(mime, make_wav()))


def test_wrong_media_type_message_form():
    result = check("audio/mpeg", make_wav())
    assert result.message == "provider response rejected: media type must be audio/wav (got audio/mpeg)"


def test_media_type_echo_is_one_line_and_safe():
    result = check("audio/mp\r\neg\x00\u4e2d", make_wav())
    assert_rejected(result)
    assert result.message.isascii() and result.message.isprintable()


@pytest.mark.parametrize("wav", [b"RIFF" + b"\xff" * 40, None], ids=["riff-garbage", "none"])
def test_rejects_unreadable_wav_without_raising(wav):
    assert_rejected(check(GOOD_MIME, wav))


def test_rejects_corrupted_data_chunk_size_without_raising():
    assert_rejected(check(GOOD_MIME, declare_frames(make_wav(), 0xFFFFFFFF)))


def test_passes_the_read_wav_frames_reason_through():
    result = check(GOOD_MIME, make_wav(channels=2))
    assert result.message == "provider response rejected: audio must be mono"


def _build_wav(frames=2400):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(bytes(frames * 2))
    return buf.getvalue()


WAV = _build_wav()


def _module():
    return sys.modules["scenevoice.synth.write_wav"]


def test_written_bytes_equal_input_wav_exactly(tmp_path):
    assert write_wav(tmp_path, 9, WAV) is None
    assert os.listdir(tmp_path) == ["009.wav"]
    assert (tmp_path / "009.wav").read_bytes() == WAV


def test_overwrites_existing_file_atomically(tmp_path):
    (tmp_path / "001.wav").write_bytes(b"old")
    assert write_wav(tmp_path, 1, WAV) is None
    assert os.listdir(tmp_path) == ["001.wav"]
    with wave.open(str(tmp_path / "001.wav")) as w:
        assert w.getnframes() == 2400


def test_write_failure_returns_violation_and_leaves_no_wav(tmp_path, monkeypatch):
    calls = []

    def fake_mkstemp(*args, **kwargs):
        calls.append(kwargs)
        raise OSError("disk full")

    monkeypatch.setattr(_module().tempfile, "mkstemp", fake_mkstemp)
    result = write_wav(tmp_path, 3, WAV)
    assert len(calls) == 1  # positive control: the patch was hit
    assert result == Violation("out-dir", "could not write 003.wav")
    assert not (tmp_path / "003.wav").exists()
    assert [n for n in os.listdir(tmp_path) if n.endswith(".wav")] == []


def test_rename_failure_returns_violation_and_cleans_up(tmp_path, monkeypatch):
    calls = []

    def fake_replace(src, dst):
        calls.append((src, dst))
        raise OSError("rename failed")

    monkeypatch.setattr(_module().os, "replace", fake_replace)
    result = write_wav(tmp_path, 4, WAV)
    assert len(calls) == 1  # positive control: the rename was reached
    assert isinstance(result, Violation)
    assert [n for n in os.listdir(tmp_path) if n.endswith(".wav")] == []
    assert os.listdir(tmp_path) == []


@pytest.mark.parametrize(("mask", "mode"), [(0o077, 0o600)])
def test_written_file_mode_follows_the_umask(tmp_path, mask, mode):
    old = os.umask(mask)
    try:
        assert write_wav(tmp_path, 6, WAV) is None
    finally:
        os.umask(old)
    assert os.stat(tmp_path / "006.wav").st_mode & 0o777 == mode


def test_leftover_temp_name_never_ends_wav(tmp_path, monkeypatch):
    removes = []

    def fake_replace(src, dst):
        raise OSError("rename failed")

    def fake_remove(path):
        removes.append(path)
        raise OSError("remove failed")

    monkeypatch.setattr(_module().os, "replace", fake_replace)
    monkeypatch.setattr(_module().os, "remove", fake_remove)
    result = write_wav(tmp_path, 10, WAV)
    monkeypatch.undo()
    assert len(removes) == 1  # positive control: cleanup was attempted
    assert isinstance(result, Violation)
    leftovers = os.listdir(tmp_path)
    assert len(leftovers) == 1  # the removal failed, so the temp file is left behind
    assert not leftovers[0].endswith(".wav")


def _scenes(n):
    return [PlanScene(i, f"T{i}", "b") for i in range(1, n + 1)]


def _put(tmp_path, ordinal, data):
    (tmp_path / "audio").mkdir(exist_ok=True)
    (tmp_path / "audio" / f"{ordinal:03d}.wav").write_bytes(data)


def _fails(result, ordinal, reason=None):
    assert isinstance(result, str)
    assert result.startswith(f"scene {ordinal}: audio/{ordinal:03d}.wav: ")
    if reason:
        assert reason in result


def test_returns_bytes_and_frames_in_plan_order(tmp_path):
    wavs = [make_wav(10), make_wav(20), make_wav(30)]
    for i, w in enumerate(wavs, 1):
        _put(tmp_path, i, w)
    result = load_scene_wavs(_scenes(3), tmp_path, 0)
    assert result == [SceneWav(w, f) for w, f in zip(wavs, (10, 20, 30), strict=True)]
    assert [r.data for r in result] == wavs


def test_missing_file(tmp_path):
    _put(tmp_path, 1, make_wav(10))
    _fails(load_scene_wavs(_scenes(2), tmp_path, 0), 2, "not a regular file")


# Security criterion 2 (outside the project): a symlinked WAV is never read.
def test_symlink_refused(tmp_path):
    _put(tmp_path, 2, make_wav(10))
    (tmp_path / "audio" / "001.wav").symlink_to(tmp_path / "audio" / "002.wav")
    _fails(load_scene_wavs(_scenes(1), tmp_path, 0), 1, "not a regular file")


@pytest.mark.parametrize(
    "data",
    [b"not a wav at all", make_wav(10, rate=16000), make_wav(0), make_wav(100)[:-50]],
    ids=["non-wav", "wrong-rate", "empty-data", "truncated"],
)
def test_invalid_wav_is_refused_naming_scene_and_file(tmp_path, data):
    _put(tmp_path, 1, data)
    _fails(load_scene_wavs(_scenes(1), tmp_path, 0), 1)


@pytest.mark.parametrize(
    ("first", "reason"),
    [(b"junk bytes", "not a readable WAV")],
    ids=["invalid-then-short"],
)
def test_earlier_read_or_invalid_failure_beats_later_short_scene(tmp_path, first, reason):
    if first is not None:
        _put(tmp_path, 1, first)
    _put(tmp_path, 2, make_wav(999))
    result = load_scene_wavs(_scenes(2), tmp_path, 1000)
    _fails(result, 1, reason)
    assert "scene 2" not in result


def test_min_frames_rejects_999_and_names_scene_and_file(tmp_path):
    _put(tmp_path, 1, make_wav(999))
    _fails(load_scene_wavs(_scenes(1), tmp_path, 1000), 1, "1000")


def test_min_frames_accepts_1000(tmp_path):
    _put(tmp_path, 1, make_wav(1000))
    result = load_scene_wavs(_scenes(1), tmp_path, 1000)
    assert isinstance(result, list) and result[0].frames == 1000


@pytest.mark.parametrize(("text", "blank"), [(" \n\t ", True), ("　", True), ("\u001c", False), (" a ", False)])
def test_blank(text, blank):
    assert is_text_blank(text) is blank


@pytest.mark.parametrize(("text", "expected"), [("a\r\nb", "a b"), ("a\n\r\n\rb", "a b"), ("a  b\tc", "a  b\tc")])
def test_one_line(text, expected):
    assert one_line(text) == expected


@pytest.mark.parametrize(("ordinal", "expected"), [(1, "001.wav"), (42, "042.wav"), (999, "999.wav")])
def test_wav_name_zero_pads_to_three_digits(ordinal, expected):
    assert wav_name(ordinal) == expected
    assert audio_rel_path(ordinal) == f"audio/{expected}"
