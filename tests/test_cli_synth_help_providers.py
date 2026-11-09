import pytest

from scenevoice.cli.main import main
from scenevoice.synth import MODELS, VOICES


@pytest.fixture
def help_text(capsys):
    with pytest.raises(SystemExit):
        main(["synth", "--help"])
    return " ".join(capsys.readouterr().out.split())


def test_lists_four_models_and_thirty_voices(help_text):
    assert len(MODELS) == 4 and len(VOICES) == 30
    assert all(name in help_text for name in (*MODELS, *VOICES))


def test_says_elevenlabs_takes_a_voice_id(help_text):
    assert "ElevenLabs voice ID" in help_text


def test_language_and_instruction_are_gemini_only(help_text):
    assert "language code, Gemini models only" in help_text
    assert "default for a Gemini model: en-GB" in help_text
    assert "delivery style instruction, Gemini models only" in help_text


def test_keeps_existing_phrases(help_text):
    for phrase in ("exact match", "30 prebuilt", "TTS model (required, no default)",
                   "no default", "--instruction=TEXT", "regenerates only scene N"):
        assert phrase in help_text
