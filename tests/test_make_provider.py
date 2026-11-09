import dataclasses
import sys

import pytest

from scenevoice.cli.main import main
from scenevoice.synth import VERTEX, ProviderError
from scenevoice.synth.make_provider import make_provider


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


def test_make_provider_returns_vertex_callable_for_vertex_model():
    env = {
        "GOOGLE_CLOUD_PROJECT": "p",
        "GOOGLE_CLOUD_LOCATION": "global",
        "VERTEX_AUTHORIZATION_KEY": "k",
    }
    assert callable(make_provider(env, "gemini-3.8-flash-tts"))


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
