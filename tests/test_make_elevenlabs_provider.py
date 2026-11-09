"""Adapter-level tests for make_elevenlabs_provider with a fake `post` (no network)."""

import inspect
import json
from pathlib import Path

import pytest

from scenevoice.synth import elevenlabs_post, make_elevenlabs_provider
from scenevoice.synth.provider import ProviderAudio, ProviderError, ProviderRequest

FIXTURES = Path(__file__).parent / "fixtures" / "elevenlabs"
KEY = "dummy-eleven-key"
RAW_KEY = " dummy-eleven-key \n"
ENV = {"ELEVENLABS_API_KEY": RAW_KEY}
VOICE = "EXAVITQu4vr4xnSDxMaL"
URL = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/with-timestamps?output_format=pcm_24000"
MODELS = ["eleven_flash_v2_5", "eleven_v4"]


def fixture(name):
    return (FIXTURES / name).read_bytes()


class FakePost:
    def __init__(self, result=None, raises=None):
        self.result = fixture("success_flash.json") if result is None else result
        self.raises = raises
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, body, timeout))
        if self.raises is not None:
            raise self.raises
        return self.result


def request():
    return ProviderRequest("It", None, "Next scene.", VOICE, None, None)


def call(post, model="eleven_flash_v2_5", env=ENV):
    return make_elevenlabs_provider(env, model, post=post)(request())


def error_of(post):
    with pytest.raises(ProviderError) as info:
        call(post)
    assert post.calls  # positive control: the fake was reached
    return info.value


def test_one_call_makes_one_post_with_stripped_key_and_timeout():
    post = FakePost()
    audio = call(post)
    assert isinstance(audio, ProviderAudio)
    assert audio.mime_type == "audio/wav"
    assert audio.alignment is not None
    assert len(post.calls) == 1
    url, headers, body, timeout = post.calls[0]
    assert url == URL
    assert headers == {"xi-api-key": KEY, "Content-Type": "application/json"}
    assert json.loads(body) == {
        "text": "It",
        "model_id": "eleven_flash_v2_5",
        "next_text": "Next scene.",
        "seed": 42,
    }
    assert timeout == 180


def test_construction_makes_no_post():
    post = FakePost()
    make_elevenlabs_provider(ENV, "eleven_flash_v2_5", post=post)
    assert post.calls == []


def test_second_call_reuses_the_model():
    post = FakePost()
    provider = make_elevenlabs_provider(ENV, "eleven_v4", post=post)
    provider(request())
    provider(request())
    assert len(post.calls) == 2
    assert [json.loads(c[2])["model_id"] for c in post.calls] == [
        "eleven_v4",
        "eleven_v4",
    ]


@pytest.mark.parametrize("model", MODELS)
def test_model_in_body_is_the_factorys_model(model):
    post = FakePost()
    call(post, model=model)
    assert json.loads(post.calls[0][2])["model_id"] == model


def test_provider_error_is_redacted_and_chained():
    cause = ProviderError(f"HTTP 401 key {KEY} and {RAW_KEY}")
    error = error_of(FakePost(raises=cause))
    assert "[redacted]" in str(error)
    assert KEY not in str(error)
    assert error.__cause__ is cause


def test_other_exception_becomes_class_name_only():
    error = error_of(FakePost(raises=RuntimeError(KEY)))
    assert str(error) == "ElevenLabs request failed: RuntimeError"


def test_parse_failure_surfaces_its_text():
    error = error_of(FakePost(result=fixture("odd_pcm.json")))
    assert str(error) == "ElevenLabs response audio has an odd byte length"


@pytest.mark.parametrize("exc", [KeyboardInterrupt, SystemExit])
def test_base_exceptions_propagate(exc):
    post = FakePost(raises=exc())
    with pytest.raises(exc):
        call(post)
    assert post.calls


def test_default_post_is_elevenlabs_post():
    assert (
        inspect.signature(make_elevenlabs_provider).parameters["post"].default
        is elevenlabs_post
    )
