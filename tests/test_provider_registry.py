import dataclasses

import pytest

import scenevoice.synth as synth
from scenevoice.synth.check_body_bytes import check_body_bytes
from scenevoice.synth.env_names import ENV_NAMES
from scenevoice.synth.make_vertex_provider import make_vertex_provider
from scenevoice.synth.models import MODELS
from scenevoice.synth.provider_registry import (
    ELEVENLABS,
    PROVIDERS,
    VERTEX,
    ProviderSpec,
    provider_for_model,
)
from scenevoice.synth.voices import VOICES


def test_registry_holds_vertex_then_elevenlabs():
    assert PROVIDERS == (VERTEX, ELEVENLABS)


def test_vertex_fields():
    assert VERTEX.models == ("gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts")
    assert VERTEX.voices == VOICES
    assert VERTEX.env_names == ENV_NAMES
    assert VERTEX.secret_env_name == "VERTEX_AUTHORIZATION_KEY"
    assert VERTEX.check_body_limit is check_body_bytes
    assert VERTEX.factory is make_vertex_provider


@pytest.mark.parametrize("model", ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"])
def test_gemini_models_resolve_to_vertex(model):
    assert provider_for_model(model) is VERTEX


@pytest.mark.parametrize("model", ["", "Gemini-3.8-flash-tts"])
def test_other_models_resolve_to_none(model):
    assert provider_for_model(model) is None


def test_models_derived_from_registry():
    assert MODELS == tuple(m for spec in PROVIDERS for m in spec.models)
    assert MODELS == (
        "gemini-3.8-flash-tts",
        "gemini-3.8-flash-lite-tts",
        "eleven_flash_v2_5",
        "eleven_v4",
    )
    assert isinstance(MODELS, tuple)


def test_spec_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        VERTEX.models = ()


def test_names_exported_from_synth():
    assert synth.ProviderSpec is ProviderSpec
    assert synth.VERTEX is VERTEX
    assert synth.PROVIDERS is PROVIDERS
    assert synth.provider_for_model is provider_for_model
    assert synth.check_body_bytes is check_body_bytes
    assert synth.Alignment.__name__ == "Alignment"
