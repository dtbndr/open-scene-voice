"""Adapter-level tests for make_vertex_provider with a fake `post` (no network).

The real urlopen call is covered only by WS10 live acceptance.
"""

import importlib
import inspect
import json
from pathlib import Path

import pytest

from scenevoice.synth import make_vertex_provider, urllib_post
from scenevoice.synth.provider import ProviderAudio, ProviderError, ProviderRequest

FIXTURES = Path(__file__).parent / "fixtures" / "vertex"
KEY = "SECRET-KEY-123"
ENV = {
    "GOOGLE_CLOUD_PROJECT": "my-proj",
    "GOOGLE_CLOUD_LOCATION": "us-central1",
    "VERTEX_AUTHORIZATION_KEY": KEY,
}
URL = (
    "https://aiplatform.googleapis.com/v1/projects/my-proj/locations/us-central1"
    "/publishers/google/models/gemini-3.8-flash-tts:generateContent"
)


def fixture(name):
    return (FIXTURES / name).read_bytes()


class FakePost:
    def __init__(self, result=None, raises=None):
        self.result = fixture("success.json") if result is None else result
        self.raises = raises
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, body, timeout))
        if self.raises is not None:
            raise self.raises
        return self.result


MODEL = "gemini-3.8-flash-tts"
MODELS = [MODEL, "gemini-3.8-flash-lite-tts"]


def call(post, env=ENV, style=None, model=MODEL):
    return make_vertex_provider(env, model, post=post)(ProviderRequest("hello", None, None, "Kore", "en-US", style))


def message_of(post, env=ENV):
    with pytest.raises(ProviderError) as info:
        call(post, env)
    assert post.calls  # positive control: the fake was reached
    return info.value


# Parse-agnostic: the provider returns the declared type and decoded bytes
# without validating them, so this L16-labelled fixture is not an acceptance case.
def test_success_returns_fixture_audio_with_one_post():
    post = FakePost()
    audio = call(post)
    assert audio == ProviderAudio("audio/L16;codec=pcm;rate=24000", b"\x01\x00\x02\x00")
    assert len(post.calls) == 1


def test_post_receives_url_key_header_and_timeout_180():
    post = FakePost()
    call(post)
    url, headers, body, timeout = post.calls[0]
    assert url == URL
    assert headers["X-goog-api-key"] == KEY
    assert b"hello" in body
    assert timeout == 180


def test_one_post_per_provider_call_and_construction_makes_none():
    post = FakePost()
    provider = make_vertex_provider(ENV, MODEL, post=post)
    assert post.calls == []
    provider(ProviderRequest("a", None, None, "Kore", "en-US", None))
    provider(ProviderRequest("b", None, None, "Kore", "en-US", "calm"))
    assert len(post.calls) == 2


def test_whitespace_is_stripped_from_project_location_and_key():
    env = {
        "GOOGLE_CLOUD_PROJECT": " my-proj\n",
        "GOOGLE_CLOUD_LOCATION": "\tus-central1 ",
        "VERTEX_AUTHORIZATION_KEY": KEY + "\n",
    }
    post = FakePost()
    call(post, env)
    url, headers, _, _ = post.calls[0]
    assert url == URL
    assert "%0A" not in url and "%20" not in url and "%09" not in url
    assert headers["X-goog-api-key"] == KEY


def captured_payload(post):
    return json.loads(post.calls[0][2].decode("utf-8"))


def test_style_reaches_the_text_part_when_given():
    post = FakePost()
    call(post, style="Say it slowly.")
    part = captured_payload(post)["contents"][0]["parts"][0]
    assert part == {"text": "hello", "speechMetadata": {"style": "Say it slowly."}}


def test_no_speech_metadata_when_style_is_none():
    post = FakePost()
    call(post, style=None)
    assert captured_payload(post)["contents"][0]["parts"][0] == {"text": "hello"}
    # positive control: the same provider does send it for a style
    styled = FakePost()
    call(styled, style="x")
    assert "speechMetadata" in captured_payload(styled)["contents"][0]["parts"][0]


@pytest.mark.parametrize("style", [None, "Say it slowly."])
def test_no_system_instruction_or_prebuilt_voice_config_in_body(style):
    post = FakePost()
    call(post, style=style)
    raw = post.calls[0][2].decode("utf-8")
    assert "systemInstruction" not in raw  # NOT sent: rejected by the 3.8 model
    assert "prebuiltVoiceConfig" not in raw
    assert captured_payload(post)["generationConfig"]["speechConfig"]["voiceConfig"] == {"voice": "Kore"}


@pytest.mark.parametrize(
    "name",
    ["bad_base64.json", "non_json.txt", "non_utf8.bin", "safety_block.json", "empty_candidates.json"],
)
def test_failure_fixtures_surface_as_provider_error(name):
    message_of(FakePost(result=fixture(name)))


@pytest.mark.parametrize("exc", [RuntimeError("boom"), ValueError("bad"), OSError("io")])
def test_other_exceptions_become_provider_error(exc):
    error = message_of(FakePost(raises=exc))
    assert type(error) is ProviderError
    assert "boom" not in str(error) and "bad" not in str(error)


@pytest.mark.parametrize("exc", [KeyboardInterrupt(), SystemExit(2)])
def test_keyboard_interrupt_and_system_exit_propagate(exc):
    post = FakePost(raises=exc)
    with pytest.raises(type(exc)):
        call(post)
    assert len(post.calls) == 1


def test_non_provider_error_with_key_gets_message_without_key():
    error = message_of(FakePost(raises=RuntimeError(f"failed with {KEY}")))
    assert KEY not in str(error)
    assert "RuntimeError" in str(error)
    assert "\n" not in str(error)


@pytest.mark.parametrize("text", [f"boom {KEY} end", f"boom {KEY}\n end"])
def test_provider_error_with_key_is_redacted_and_chained(text):
    original = ProviderError(text)
    error = message_of(FakePost(raises=original))
    assert KEY not in str(error)
    assert "[redacted]" in str(error)
    assert error is not original
    assert error.__cause__ is original


def test_unstripped_key_form_is_redacted():
    env = dict(ENV, VERTEX_AUTHORIZATION_KEY=KEY + "\n")
    error = message_of(FakePost(raises=ProviderError(f"x {KEY}\n y")), env)
    assert KEY not in str(error)
    error = message_of(FakePost(raises=ProviderError(f"x {KEY} y")), env)
    assert KEY not in str(error)


def test_http_error_body_containing_key_is_redacted():
    error = message_of(FakePost(raises=ProviderError(f"HTTP 403 key {KEY} is invalid")))
    assert str(error).startswith("HTTP 403")
    assert KEY not in str(error)


def test_parse_failure_message_has_no_key():
    body = f'{{"candidates": "{KEY}"}}'.encode()
    error = message_of(FakePost(result=body))
    assert KEY not in str(error)


def test_unexpected_parse_exception_is_wrapped_without_text(monkeypatch):
    module = importlib.import_module("scenevoice.synth.make_vertex_provider")

    def explode(raw):
        raise RuntimeError(f"leak {KEY}")

    monkeypatch.setattr(module, "parse_vertex_response", explode)
    error = message_of(FakePost())
    assert KEY not in str(error)
    assert "RuntimeError" in str(error)


@pytest.mark.parametrize("model", MODELS)
def test_post_goes_to_the_url_carrying_the_model(model):
    post = FakePost()
    call(post, model=model)
    assert len(post.calls) == 1
    assert post.calls[0][0] == URL.replace(MODEL, model)


def test_second_provider_call_reuses_the_same_model():
    post = FakePost()
    provider = make_vertex_provider(ENV, MODELS[1], post=post)
    provider(ProviderRequest("a", None, None, "Kore", "en-US", None))
    provider(ProviderRequest("b", None, None, "Kore", "en-US", None))
    assert [c[0] for c in post.calls] == [URL.replace(MODEL, MODELS[1])] * 2


@pytest.mark.parametrize("model", MODELS)
def test_model_never_appears_in_the_body(model):
    post = FakePost()
    call(post, model=model)
    assert model not in post.calls[0][2].decode("utf-8")


def test_default_post_is_urllib_post():
    default = inspect.signature(make_vertex_provider).parameters["post"].default
    assert default is urllib_post
