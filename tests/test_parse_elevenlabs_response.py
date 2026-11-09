import base64
import json
from pathlib import Path

import pytest

from scenevoice.synth import (
    ProviderAudio,
    ProviderError,
    parse_elevenlabs_response,
    read_wav_frames,
    validate_audio,
)

FIXTURES = Path(__file__).parent / "fixtures" / "elevenlabs"


def _raw(name):
    return (FIXTURES / name).read_bytes()


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


def test_normalized_alignment_is_ignored():
    assert parse_elevenlabs_response(_raw("normalized_ignored.json")).alignment is not None


def test_lone_surrogate_character_is_accepted():
    audio = parse_elevenlabs_response(_raw("lone_surrogate_character.json"))
    assert audio.alignment is not None
    assert audio.alignment.characters[0] == "\ud83d"


_P = "ElevenLabs response "
_TIMES = _P + "alignment times must be finite non-negative numbers"
NEGATIVES = {
    "non_utf8.bin": _P + "is not UTF-8",
    "utf16_json.bin": _P + "is not UTF-8",
    "non_json.txt": _P + "is not valid JSON",
    "top_level_array.json": _P + "is not a JSON object",
    "missing_audio.json": _P + "audio_base64 is not a string",
    "non_string_audio.json": _P + "audio_base64 is not a string",
    "bad_base64.json": _P + "audio_base64 is not valid base64",
    "empty_pcm.json": _P + "audio is empty",
    "odd_pcm.json": _P + "audio has an odd byte length",
    "missing_alignment.json": _P + "alignment is not an object",
    "null_alignment.json": _P + "alignment is not an object",
    "alignment_not_object.json": _P + "alignment is not an object",
    "missing_array.json": _P + "alignment arrays are missing or not arrays",
    "array_not_list.json": _P + "alignment arrays are missing or not arrays",
    "unequal_arrays.json": _P + "alignment arrays differ in length",
    "empty_arrays.json": _P + "alignment is empty",
    "non_string_character.json": _P + "alignment characters must be strings",
    "negative_time.json": _TIMES,
    "boolean_time.json": _TIMES,
    "string_time.json": _TIMES,
    "nan_time.json": _TIMES,
    "huge_time.json": _TIMES,
    "huge_int_time.json": _TIMES,
}


@pytest.mark.parametrize(("name", "text"), sorted(NEGATIVES.items()))
def test_negative_fixture_raises_its_exact_text(name, text):
    with pytest.raises(ProviderError) as info:
        parse_elevenlabs_response(_raw(name))
    assert str(info.value) == text


@pytest.mark.parametrize("name", sorted(NEGATIVES))
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
