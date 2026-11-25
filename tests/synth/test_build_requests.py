import json

import pytest

from scenevoice.synth import ProviderRequest, build_elevenlabs_request
from scenevoice.synth.build_vertex_request import build_vertex_request

VOICE = "EXAVITQu4vr4xnSDxMaL"


BASE = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/with-timestamps?output_format=pcm_24000"


def _req(body="Hello.", previous=None, nxt=None, voice=VOICE):
    return ProviderRequest(body, previous, nxt, voice, None, None)


def _body(raw):
    return json.loads(raw.decode("utf-8"))


def test_url_is_exact_for_a_plain_voice_id():
    assert build_elevenlabs_request("k", "eleven_flash_v2_5", _req())[0] == BASE


def test_voice_is_quoted_so_it_cannot_change_the_path_or_query():
    url = build_elevenlabs_request("k", "eleven_v4", _req(voice="a/b?c#d"))[0]
    assert url == (
        "https://api.elevenlabs.io/v1/text-to-speech/a%2Fb%3Fc%23d/with-timestamps?output_format=pcm_24000"
    )


@pytest.mark.parametrize(
    ("previous", "nxt", "keys"),
    [
        ("P", "N", ["text", "model_id", "previous_text", "next_text", "seed"]),
        (None, "N", ["text", "model_id", "next_text", "seed"]),
        ("P", None, ["text", "model_id", "previous_text", "seed"]),
        (None, None, ["text", "model_id", "seed"]),
    ],
)
def test_body_key_order_follows_the_neighbours(previous, nxt, keys):
    raw = build_elevenlabs_request("k", "eleven_v4", _req(previous=previous, nxt=nxt))[2]
    assert list(_body(raw)) == keys


def test_text_is_verbatim_and_non_ascii_is_written_as_itself():
    text = "  Café 你好\n\ttab  "
    raw = build_elevenlabs_request("k", "eleven_v4", _req(body=text))[2]
    assert _body(raw)["text"] == text
    assert "é".encode() in raw
    assert b"\\u" not in raw


@pytest.mark.parametrize("model", ["eleven_flash_v2_5", "eleven_v4"])
def test_model_id_is_the_model_and_seed_is_the_integer_42(model):
    body = _body(build_elevenlabs_request("k", model, _req())[2])
    assert body["model_id"] == model
    assert body["seed"] == 42
    assert type(body["seed"]) is int


def test_long_neighbours_are_not_truncated():
    long = "x" * 50_000
    body = _body(build_elevenlabs_request("k", "eleven_v4", _req(previous=long, nxt=long))[2])
    assert body["previous_text"] == long
    assert body["next_text"] == long


def test_language_and_instruction_are_never_sent():
    request = ProviderRequest("Hi", "P", "N", VOICE, "en-US", "calm")
    body = _body(build_elevenlabs_request("k", "eleven_v4", request)[2])
    assert set(body) == {"text", "model_id", "previous_text", "next_text", "seed"}


MODELS = ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"]


def build(
    project="proj-1",
    location="global",
    key="k",
    body="Hello",
    voice="Kore",
    language="en-US",
    style=None,
    model="gemini-3.8-flash-tts",
):
    return build_vertex_request(project, location, key, body, voice, language, style, model)


def payload(**kwargs):
    _, _, raw = build(**kwargs)
    return json.loads(raw.decode("utf-8"))


def keys_anywhere(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from keys_anywhere(value)
    elif isinstance(node, list):
        for item in node:
            yield from keys_anywhere(item)


def test_url_matches_template():
    url, _, _ = build()
    assert url == (
        "https://aiplatform.googleapis.com/v1/projects/proj-1/locations/global"
        "/publishers/google/models/gemini-3.8-flash-tts:generateContent"
    )


def test_project_and_location_are_quoted():
    url, _, _ = build(project="a/b?c#d e", location="x/y?z#w v")
    assert url == (
        "https://aiplatform.googleapis.com/v1/projects/a%2Fb%3Fc%23d%20e"
        "/locations/x%2Fy%3Fz%23w%20v/publishers/google/models/"
        "gemini-3.8-flash-tts:generateContent"
    )


def test_headers_carry_key_and_content_type():
    _, headers, _ = build(key="secret-key")
    assert headers == {"X-goog-api-key": "secret-key", "Content-Type": "application/json"}


def test_body_has_exact_structure_without_style():
    assert payload(body="Say it", voice="Puck", language="de-DE") == {
        "contents": [{"role": "user", "parts": [{"text": "Say it"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "languageCode": "de-DE",
                "voiceConfig": {"voice": "Puck"},
            },
        },
    }


def test_body_has_exact_structure_with_style():
    assert payload(body="Say it", voice="Puck", language="de-DE", style="Slowly.") == {
        "contents": [
            {"role": "user", "parts": [{"text": "Say it", "speechMetadata": {"style": "Slowly."}}]}
        ],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "languageCode": "de-DE",
                "voiceConfig": {"voice": "Puck"},
            },
        },
    }


def test_no_prebuilt_voice_config_or_system_instruction_is_sent():
    for style in (None, "Slowly."):
        names = set(keys_anywhere(payload(style=style)))
        assert "prebuiltVoiceConfig" not in names
        assert "systemInstruction" not in names  # NOT sent: rejected by the 3.8 model


def test_non_ascii_text_round_trips_unescaped():
    text = "Grüße 日本語 \U0001f600"
    _, _, raw = build(body=text)
    assert isinstance(raw, bytes)
    assert text.encode("utf-8") in raw
    assert json.loads(raw)["contents"][0]["parts"][0]["text"] == text


@pytest.mark.parametrize("model", MODELS)
def test_url_carries_the_model_in_the_path(model):
    url, _, _ = build(model=model)
    assert url == (
        "https://aiplatform.googleapis.com/v1/projects/proj-1/locations/global"
        f"/publishers/google/models/{model}:generateContent"
    )
