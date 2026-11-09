import dataclasses

import pytest

from scenevoice.synth.provider import (
    Provider,
    ProviderAudio,
    ProviderError,
    ProviderFactory,
    ProviderRequest,
)


def test_provider_audio_holds_fields():
    audio = ProviderAudio("audio/wav", b"\x00\x01")
    assert audio.mime_type == "audio/wav"
    assert audio.wav == b"\x00\x01"


def test_provider_audio_is_frozen():
    audio = ProviderAudio("audio/wav", b"")
    with pytest.raises(dataclasses.FrozenInstanceError):
        audio.wav = b"x"  # type: ignore[misc]


def test_provider_error_is_exception_carrying_message():
    err = ProviderError("boom")
    assert isinstance(err, Exception)
    assert str(err) == "boom"
    with pytest.raises(ProviderError, match="boom"):
        raise err


def test_aliases_are_importable_and_usable():
    def provider(request: ProviderRequest) -> ProviderAudio:
        return ProviderAudio("audio/wav", b"\x00\x00")

    def factory(env: dict[str, str], model: str) -> Provider:
        return provider

    f: ProviderFactory = factory
    assert f({}, "m")(ProviderRequest("t", None, None, "v", "l", None)).wav == b"\x00\x00"


def test_names_exported_from_package():
    import scenevoice.synth as synth

    for name in ("Provider", "ProviderAudio", "ProviderError", "ProviderFactory", "validate_audio"):
        assert hasattr(synth, name)
