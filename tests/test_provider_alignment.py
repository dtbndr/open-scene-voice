import dataclasses

import pytest

import scenevoice.synth as synth
from scenevoice.synth.alignment import Alignment
from scenevoice.synth.provider import ProviderAudio


def make_alignment():
    return Alignment(("a", "b"), (0.0, 0.1), (0.1, 0.2))


def test_alignment_defaults_to_none():
    assert ProviderAudio("audio/wav", b"x").alignment is None


def test_provider_audio_accepts_alignment_keyword():
    alignment = make_alignment()
    assert ProviderAudio("audio/wav", b"x", alignment=alignment).alignment is alignment


def test_alignment_field_names():
    names = [f.name for f in dataclasses.fields(Alignment)]
    assert names == ["characters", "character_start_times_seconds", "character_end_times_seconds"]


def test_alignment_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        make_alignment().characters = ()


def test_provider_audio_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        ProviderAudio("audio/wav", b"x").alignment = make_alignment()


def test_importable_from_synth():
    assert synth.Alignment is Alignment
    assert synth.ProviderAudio is ProviderAudio
