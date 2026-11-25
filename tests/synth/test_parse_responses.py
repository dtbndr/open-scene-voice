import base64
import io
import json
import wave

import paths_helper
import pytest

from scenevoice.synth import (
    Alignment,
    ProviderAudio,
    ProviderError,
    accept_alignment,
    clamp_alignment,
    parse_elevenlabs_response,
    pcm_to_wav,
    read_wav_frames,
    validate_audio,
)
from scenevoice.synth.parse_vertex_response import parse_vertex_response

VERTEX_FIXTURES = paths_helper.FIXTURES / "vertex"


PCM = b"\x01\x00\x02\x00"


MIME = "audio/L16;codec=pcm;rate=24000"


def load(name):
    return (VERTEX_FIXTURES / name).read_bytes()


def test_success_returns_exact_mime_and_pcm():
    assert parse_vertex_response(load("success.json")) == ProviderAudio(MIME, PCM)


def test_first_part_with_inline_data_is_used_after_text_parts():
    assert parse_vertex_response(load("text_then_audio.json")) == ProviderAudio(MIME, PCM)


FAILURES = ["non_json.txt", "bad_base64.json", "no_inline_data.json", "safety_block.json"]


@pytest.mark.parametrize("name", FAILURES)
def test_unexpected_response_raises_exactly_provider_error(name):
    raw = load(name)
    with pytest.raises(Exception) as caught:
        parse_vertex_response(raw)
    error = caught.value
    assert type(error) is ProviderError
    message = str(error)
    assert message and "\n" not in message and "\r" not in message
    assert raw.decode("utf-8", "replace").strip() not in message


def test_audio_rules_are_left_to_validate_audio():
    assert parse_vertex_response(load("odd_pcm.json")) == ProviderAudio(
        "audio/L16;rate=24000", b"\x01\x00\x02"
    )


def _message(doc):
    with pytest.raises(ProviderError) as caught:
        parse_vertex_response(json.dumps(doc).encode())
    return str(caught.value)


def test_prompt_block_reason_is_reported():
    doc = {"candidates": [], "promptFeedback": {"blockReason": "PROHIBITED_CONTENT"}}
    assert _message(doc) == "Vertex response has no candidates (blockReason: PROHIBITED_CONTENT)"


def test_candidate_finish_reason_is_reported():
    doc = {"candidates": [{"finishReason": "SAFETY"}]}
    assert _message(doc) == "Vertex response candidate has no content (finishReason: SAFETY)"


HOSTILE = ["line\nbreak", "x" * 65, 7]


@pytest.mark.parametrize("value", HOSTILE)
def test_non_matching_reasons_are_ignored(value):
    no_candidates = {"candidates": [], "promptFeedback": {"blockReason": value}}
    assert _message(no_candidates) == "Vertex response has no candidates"
    no_content = {"candidates": [{"finishReason": value}]}
    assert _message(no_content) == "Vertex response candidate has no content"


def test_wav_response_returns_decoded_wav_bytes():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setframerate(24000)
        w.setnchannels(1)
        w.setsampwidth(2)
        w.writeframes(bytes(20))
    wav = buf.getvalue()
    data = base64.b64encode(wav).decode()
    doc = {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/wav", "data": data}}]}}]}
    assert parse_vertex_response(json.dumps(doc).encode()) == ProviderAudio("audio/wav", wav)


EL_FIXTURES = paths_helper.FIXTURES / "elevenlabs"


def _raw(name):
    return (EL_FIXTURES / name).read_bytes()


def test_flash_success_is_accepted_wav_with_the_input_alignment():
    raw = _raw("success_flash.json")
    audio = parse_elevenlabs_response(raw)
    doc = json.loads(raw)["alignment"]
    assert isinstance(audio, ProviderAudio)
    assert audio.mime_type == "audio/wav"
    assert validate_audio(audio) is None
    assert read_wav_frames(audio.wav) == 4800
    assert audio.alignment is not None
    assert list(audio.alignment.characters) == doc["characters"]
    assert list(audio.alignment.character_start_times_seconds) == doc["character_start_times_seconds"]
    assert list(audio.alignment.character_end_times_seconds) == doc["character_end_times_seconds"]


def test_v4_overshoot_is_clamped_to_the_audio_duration():
    audio = parse_elevenlabs_response(_raw("success_v4_overshoot.json"))
    assert read_wav_frames(audio.wav) == 3600
    assert audio.alignment is not None
    assert audio.alignment.character_start_times_seconds == (0.0, 0.08, 0.15)
    assert audio.alignment.character_end_times_seconds == (0.08, 0.15, 0.15)


def test_lone_surrogate_character_is_accepted():
    audio = parse_elevenlabs_response(_raw("lone_surrogate_character.json"))
    assert audio.alignment is not None
    assert audio.alignment.characters[0] == "\ud83d"


_P = "ElevenLabs response "


_TIMES = _P + "alignment times must be finite non-negative numbers"


# P0 (paid audio): a provider body with corrupt or empty audio is never written
# as a WAV. One row per failure class (body, audio, alignment shape, times).
NEGATIVES = {
    "non_json.txt": _P + "is not valid JSON",
    "bad_base64.json": _P + "audio_base64 is not valid base64",
    "empty_pcm.json": _P + "audio is empty",
    "odd_pcm.json": _P + "audio has an odd byte length",
    "missing_alignment.json": _P + "alignment is not an object",
    "unequal_arrays.json": _P + "alignment arrays differ in length",
    "negative_time.json": _TIMES,
    "nan_time.json": _TIMES,
}


@pytest.mark.parametrize(("name", "text"), sorted(NEGATIVES.items()))
def test_negative_fixture_raises_its_exact_text(name, text):
    with pytest.raises(ProviderError) as info:
        parse_elevenlabs_response(_raw(name))
    assert str(info.value) == text


@pytest.mark.parametrize("name", ["bad_base64.json", "odd_pcm.json"])
def test_message_never_contains_the_audio_text(name):
    raw = _raw(name)
    try:
        audio_text = json.loads(raw.decode("utf-8")).get("audio_base64")
    except (ValueError, AttributeError):
        audio_text = None
    with pytest.raises(ProviderError) as info:
        parse_elevenlabs_response(raw)
    if isinstance(audio_text, str) and audio_text:
        assert audio_text not in str(info.value)
    assert base64.b64encode(b"\x00\x00").decode() not in str(info.value)


def test_pcm_wrap_is_a_readable_24k_mono_16bit_wav():
    pcm = b"\x00\x00" * 10
    wav = pcm_to_wav(pcm)
    assert read_wav_frames(wav) == 10
    with wave.open(io.BytesIO(wav), "rb") as reader:
        assert (reader.getframerate(), reader.getnchannels(), reader.getsampwidth()) == (24000, 1, 2)
        assert reader.readframes(reader.getnframes()) == pcm


FIXTURES = paths_helper.FIXTURES / "elevenlabs"


NOT_OBJECT = "alignment is not an object"


ARRAYS = "alignment arrays are missing or not arrays"


TIMES = "alignment times must be finite non-negative numbers"


def _good():
    return {
        "characters": ["I", "t"],
        "character_start_times_seconds": [0.0, 0.128],
        "character_end_times_seconds": [0.128, 0.186],
    }


def _with(**changes):
    value = _good()
    value.update(changes)
    return value


def test_flash_fixture_arrays_give_tuples():
    doc = json.loads((FIXTURES / "success_flash.json").read_bytes())
    assert accept_alignment(doc["alignment"]) == Alignment(("I", "t"), (0.0, 0.128), (0.128, 0.186))


def test_integer_time_becomes_float():
    result = accept_alignment(_with(character_start_times_seconds=[0, 1]))
    assert isinstance(result, Alignment)
    assert result.character_start_times_seconds == (0.0, 1.0)
    assert all(type(t) is float for t in result.character_start_times_seconds)


def _missing(key):
    value = _good()
    del value[key]
    return value


# P1 (align): bad alignment never reaches the record. Lowest layer; one row per class.
@pytest.mark.parametrize(
    ("value", "reason"),
    [
        (None, NOT_OBJECT),
        (_missing("characters"), ARRAYS),
        (_with(character_end_times_seconds=[0.128]), "alignment arrays differ in length"),
        (
            {"characters": [], "character_start_times_seconds": [], "character_end_times_seconds": []},
            "alignment is empty",
        ),
        (_with(characters=["I", 7]), "alignment characters must be strings"),
        (_with(character_end_times_seconds=[0.1, -1]), TIMES),
        (_with(character_start_times_seconds=[float("nan"), 0.1]), TIMES),
        (_with(character_start_times_seconds=[True, 0.1]), TIMES),
    ],
)
def test_rejected_with_exact_reason(value, reason):
    assert accept_alignment(value) == reason


def make_alignment():
    return Alignment(("a", "b"), (0.0, 0.1), (0.1, 0.2))


def _v4():
    return Alignment(("I", "t", " "), (0.0, 0.08, 0.16), (0.08, 0.16, 0.24))


def test_times_beyond_duration_are_clamped():
    result = clamp_alignment(_v4(), 0.15)
    assert result.character_start_times_seconds == (0.0, 0.08, 0.15)
    assert result.character_end_times_seconds == (0.08, 0.15, 0.15)
