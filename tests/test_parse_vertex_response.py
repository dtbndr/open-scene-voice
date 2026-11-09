import base64
import io
import json
import wave
from pathlib import Path

import pytest

from scenevoice.synth.parse_vertex_response import parse_vertex_response
from scenevoice.synth.provider import ProviderAudio, ProviderError

FIXTURES = Path(__file__).parent / "fixtures" / "vertex"
PCM = b"\x01\x00\x02\x00"
MIME = "audio/L16;codec=pcm;rate=24000"


def load(name):
    return (FIXTURES / name).read_bytes()


def test_success_returns_exact_mime_and_pcm():
    assert parse_vertex_response(load("success.json")) == ProviderAudio(MIME, PCM)


def test_first_part_with_inline_data_is_used_after_text_parts():
    assert parse_vertex_response(load("text_then_audio.json")) == ProviderAudio(MIME, PCM)


FAILURES = [
    "missing_parts.json",
    "no_inline_data.json",
    "bad_base64.json",
    "non_json.txt",
    "non_string_data.json",
    "non_string_mime.json",
    "non_utf8.bin",
    "top_level_array.json",
    "empty_candidates.json",
    "part_not_object.json",
    "inline_data_not_object.json",
    "safety_block.json",
]


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


@pytest.mark.parametrize(
    ("name", "mime", "pcm"),
    [
        ("mpeg_mime.json", "audio/mpeg", PCM),
        ("empty_pcm.json", "audio/L16;rate=24000", b""),
        ("odd_pcm.json", "audio/L16;rate=24000", b"\x01\x00\x02"),
    ],
)
def test_audio_rules_are_left_to_validate_audio(name, mime, pcm):
    assert parse_vertex_response(load(name)) == ProviderAudio(mime, pcm)


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


HOSTILE = ["has space", "line\nbreak", "x" * 65, "", 7, None, ["SAFETY"], "SAFE-TY", "SAFETY\n"]


@pytest.mark.parametrize("value", HOSTILE)
def test_non_matching_reasons_are_ignored(value):
    no_candidates = {"candidates": [], "promptFeedback": {"blockReason": value}}
    assert _message(no_candidates) == "Vertex response has no candidates"
    no_content = {"candidates": [{"finishReason": value}]}
    assert _message(no_content) == "Vertex response candidate has no content"


def test_reason_of_64_characters_is_accepted():
    value = "A" * 64
    doc = {"candidates": [{"finishReason": value}]}
    assert _message(doc).endswith(f"(finishReason: {value})")


def test_non_dict_prompt_feedback_is_ignored():
    doc = {"candidates": [], "promptFeedback": "SAFETY"}
    assert _message(doc) == "Vertex response has no candidates"


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
