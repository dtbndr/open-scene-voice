import json

import pytest

from scenevoice.synth import ProviderRequest, build_elevenlabs_request

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


def test_headers_are_exactly_key_and_content_type():
    headers = build_elevenlabs_request("the-key", "eleven_v4", _req())[1]
    assert headers == {"xi-api-key": "the-key", "Content-Type": "application/json"}


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
