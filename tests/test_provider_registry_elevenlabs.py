import dataclasses
import sys

import pytest

import scenevoice.synth as synth
from scenevoice.synth.check_body_chars import check_body_chars
from scenevoice.synth.check_limits import check_limits
from scenevoice.synth.check_model import check_model
from scenevoice.synth.env_names import ELEVENLABS_ENV_NAMES
from scenevoice.synth.limits import ELEVENLABS_CHAR_LIMITS
from scenevoice.synth.make_elevenlabs_provider import make_elevenlabs_provider
from scenevoice.synth.make_provider import make_provider
from scenevoice.synth.models import MODELS
from scenevoice.synth.plan_scene import PlanScene
from scenevoice.synth.provider_registry import (
    ELEVENLABS,
    PROVIDERS,
    VERTEX,
    provider_for_model,
)
from scenevoice.validation import Violation

FOUR = (
    "gemini-3.8-flash-tts",
    "gemini-3.8-flash-lite-tts",
    "eleven_flash_v2_5",
    "eleven_v4",
)


def test_registry_holds_vertex_then_elevenlabs():
    assert PROVIDERS == (VERTEX, ELEVENLABS)


def test_elevenlabs_fields():
    assert ELEVENLABS.models == ("eleven_flash_v2_5", "eleven_v4")
    assert ELEVENLABS.voices is None
    assert ELEVENLABS.env_names == ("ELEVENLABS_API_KEY",) == ELEVENLABS_ENV_NAMES
    assert ELEVENLABS.secret_env_name == "ELEVENLABS_API_KEY"
    assert ELEVENLABS.check_body_limit is check_body_chars
    assert ELEVENLABS.factory is make_elevenlabs_provider


def test_char_limits():
    assert ELEVENLABS_CHAR_LIMITS == {"eleven_flash_v2_5": 40000, "eleven_v4": 10000}


@pytest.mark.parametrize("model", ["eleven_flash_v2_5", "eleven_v4"])
def test_elevenlabs_models_resolve(model):
    assert provider_for_model(model) is ELEVENLABS


@pytest.mark.parametrize("model", ["eleven_v3", "eleven_multilingual_v2", "Eleven_v4"])
def test_other_eleven_names_resolve_to_none(model):
    assert provider_for_model(model) is None


def test_models_four_tuple():
    assert MODELS == FOUR


def test_check_model_text_names_four():
    violation = check_model("eleven_v3")
    assert violation == Violation("synth-option", "model must be one of " + ", ".join(FOUR))


def test_make_provider_builds_elevenlabs_callable_without_a_call():
    assert callable(make_provider({"ELEVENLABS_API_KEY": "k"}, "eleven_flash_v2_5"))


def test_make_provider_hands_env_and_model_to_the_factory(monkeypatch):
    calls = []
    sentinel = object()

    def factory(env, model):
        calls.append((env, model))
        return sentinel

    stand_in = dataclasses.replace(ELEVENLABS, factory=factory)
    module = sys.modules["scenevoice.synth.make_provider"]
    monkeypatch.setattr(module, "provider_for_model", lambda model: stand_in)
    env = {"ELEVENLABS_API_KEY": "k"}
    assert make_provider(env, "eleven_v4") is sentinel
    assert calls == [(env, "eleven_v4")]


def test_check_limits_reports_count_first_then_characters():
    many = [PlanScene(n, "", "a" * 10001) for n in range(1, 1001)]
    bound = lambda s: check_body_chars(s, "eleven_v4")  # noqa: E731
    assert check_limits(many, body_check=bound) == Violation(
        "synth-limit", "1000 scenes exceeds the maximum of 999"
    )
    assert check_limits(many[:1], body_check=bound) == Violation(
        "synth-limit", "body over 10000 characters: scene 1: 10001 characters"
    )


def test_exported_from_synth():
    assert synth.ELEVENLABS is ELEVENLABS
    assert synth.check_body_chars is check_body_chars
    assert synth.ELEVENLABS_ENV_NAMES is ELEVENLABS_ENV_NAMES
