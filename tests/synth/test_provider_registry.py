"""run_preflight and run_synth pass the provider spec through: its key names, its body check, the model."""

import dataclasses
import io
import json
import sys

import pytest
from common_helper import Stdin

from scenevoice.cli.main import main
from scenevoice.synth import (
    VERTEX,
    ProviderError,
    ProviderRequest,
    make_vertex_provider,
    run_preflight,
    run_synth,
)
from scenevoice.synth.check_body_chars import check_body_chars
from scenevoice.synth.check_limits import check_limits
from scenevoice.synth.check_model import check_model
from scenevoice.synth.env_names import ELEVENLABS_ENV_NAMES
from scenevoice.synth.limits import ELEVENLABS_CHAR_LIMITS
from scenevoice.synth.make_elevenlabs_provider import make_elevenlabs_provider
from scenevoice.synth.make_provider import make_provider
from scenevoice.synth.plan_scene import PlanScene
from scenevoice.synth.provider_registry import ELEVENLABS, provider_for_model
from scenevoice.validation import Violation

FOUR = (
    "gemini-3.8-flash-tts",
    "gemini-3.8-flash-lite-tts",
    "eleven_flash_v2_5",
    "eleven_v4",
)


def test_elevenlabs_fields():
    assert ELEVENLABS.models == ("eleven_flash_v2_5", "eleven_v4")
    assert ELEVENLABS.voices is None
    assert ELEVENLABS.env_names == ("ELEVENLABS_API_KEY",) == ELEVENLABS_ENV_NAMES
    assert ELEVENLABS.secret_env_name == "ELEVENLABS_API_KEY"
    assert ELEVENLABS.check_body_limit is check_body_chars
    assert ELEVENLABS.factory is make_elevenlabs_provider


def test_char_limits():
    assert ELEVENLABS_CHAR_LIMITS == {"eleven_flash_v2_5": 40000, "eleven_v4": 10000}


@pytest.mark.parametrize(
    ("model", "spec"),
    [
        ("gemini-3.8-flash-tts", VERTEX),
        ("eleven_v4", ELEVENLABS),
    ],
)
def test_known_models_resolve_to_their_provider(model, spec):
    assert provider_for_model(model) is spec


@pytest.mark.parametrize(
    "model",
    ["", "eleven_v3"],
)
def test_other_models_resolve_to_none(model):
    assert provider_for_model(model) is None


def test_check_model_text_names_four():
    violation = check_model("eleven_v3")
    assert violation == Violation("synth-option", "model must be one of " + ", ".join(FOUR))


def test_check_limits_reports_count_first_then_characters():
    many = [PlanScene(n, "", "a" * 10001) for n in range(1, 1001)]
    bound = lambda s: check_body_chars(s, "eleven_v4")  # noqa: E731
    assert check_limits(many, body_check=bound) == Violation(
        "synth-limit", "1000 scenes exceeds the maximum of 999"
    )
    assert check_limits(many[:1], body_check=bound) == Violation(
        "synth-limit", "body over 10000 characters: scene 1: 10001 characters"
    )


ENV = {
    "GOOGLE_CLOUD_PROJECT": "my-proj",
    "GOOGLE_CLOUD_LOCATION": "us-central1",
    "VERTEX_AUTHORIZATION_KEY": "SECRET-KEY-123",
}


MODEL = "gemini-3.8-flash-tts"


class FakePost:
    def __init__(self):
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, body, timeout))
        return json.dumps({"candidates": [{"content": {"parts": [{"inlineData": {
            "mimeType": "audio/wav", "data": "AAAA"}}]}}]}).encode()


def send(request):
    post = FakePost()
    provider = make_vertex_provider(ENV, MODEL, post=post)
    try:
        provider(request)
    except Exception:
        pass
    assert len(post.calls) == 1
    return post.calls[0]


def test_vertex_ignores_neighbour_fields():
    bare = send(ProviderRequest("body", None, None, "Kore", "en-US", "Say:"))
    full = send(ProviderRequest("body", "before", "after", "Kore", "en-US", "Say:"))
    assert bare == full


def test_vertex_sends_body_voice_language_and_style_in_the_body():
    _, _, payload, _ = send(ProviderRequest("hello body", "p", "n", "Charon", "en-GB", "Calm"))
    text = payload.decode()
    for part in ("hello body", "Charon", "en-GB", "Calm"):
        assert part in text
    assert "\"p\"" not in text and "\"n\"" not in text


def test_vertex_without_language_raises_provider_error():
    provider = make_vertex_provider(ENV, MODEL, post=FakePost())
    with pytest.raises(ProviderError, match="Vertex request has no language"):
        provider(ProviderRequest("b", None, None, "Kore", None, None))


def test_make_provider_calls_owning_spec_factory(monkeypatch):
    calls = []
    sentinel = object()

    def factory(env, model):
        calls.append((env, model))
        return sentinel

    stand_in = dataclasses.replace(VERTEX, factory=factory)
    module = sys.modules["scenevoice.synth.make_provider"]
    monkeypatch.setattr(module, "provider_for_model", lambda model: stand_in)
    env = {"A": "b"}
    assert make_provider(env, "m") is sentinel
    assert calls == [(env, "m")]


def test_make_provider_unknown_model_raises_provider_error():
    with pytest.raises(ProviderError):
        make_provider({}, "nope")


def test_main_synth_defaults_to_make_provider(monkeypatch):
    seen = []

    def recorder(args, factory):
        seen.append(factory)
        return 0

    monkeypatch.setattr(sys.modules["scenevoice.cli.main"], "run_synth_command", recorder)
    code = main(["synth", "--voice", "Charon", "--model", "gemini-3.8-flash-tts", "--out", "o"])
    assert seen, "run_synth_command was not called"
    assert code == 0
    assert seen[0] is make_provider


WIRING_ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": "SeCrEt-key-0123456789",
}


PLAN = json.dumps({"scenes": [{"ordinal": 1, "title": "t", "body": "hello"}]})


def test_preflight_uses_the_spec_key_names(tmp_path):
    fake = dataclasses.replace(VERTEX, env_names=("FAKE_KEY",))
    result = run_preflight(None, Stdin(PLAN), {}, tmp_path / ".env", tmp_path / "out", spec=fake)
    assert result.startswith("Missing:") and "FAKE_KEY" in result


def test_preflight_applies_the_body_check(tmp_path):
    seen = []

    def fake(items):
        seen.append(items)
        return Violation("x", "stop here")

    result = run_preflight(None, Stdin(PLAN), WIRING_ENV, tmp_path / ".env", tmp_path / "out", body_check=fake)
    assert result == "stop here" and len(seen) == 1


def test_run_synth_binds_the_model_into_the_body_check(tmp_path, monkeypatch):
    received = []

    def check(items, model):
        received.append((list(items), model))
        return Violation("x", "stop here")

    stand_in = dataclasses.replace(VERTEX, check_body_limit=check)
    monkeypatch.setattr(sys.modules["scenevoice.synth.run_synth"], "provider_for_model", lambda model: stand_in)
    err = io.StringIO()
    code = run_synth(
        None, Stdin(PLAN), WIRING_ENV, tmp_path / ".env", tmp_path / "out",
        "Charon", MODEL, "en-GB", None, lambda env, model: None, err,
    )  # fmt: skip
    assert code == 1 and err.getvalue() == "scenevoice synth: FAIL stop here\n"
    assert len(received) == 1
    assert received[0][1] == MODEL and received[0][0][0].body == "hello"
