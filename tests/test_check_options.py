import pytest

from scenevoice.synth.check_instruction import check_instruction
from scenevoice.synth.check_language import check_language
from scenevoice.synth.check_voice import check_voice
from scenevoice.synth.defaults import DEFAULT_LANGUAGE
from scenevoice.synth.voices import VOICES
from scenevoice.validation import Violation

CONTRACT_VOICES = [
    "Achernar",
    "Achird",
    "Algenib",
    "Algieba",
    "Alnilam",
    "Aoede",
    "Autonoe",
    "Callirrhoe",
    "Charon",
    "Despina",
    "Enceladus",
    "Erinome",
    "Fenrir",
    "Gacrux",
    "Iapetus",
    "Kore",
    "Laomedeia",
    "Leda",
    "Orus",
    "Puck",
    "Pulcherrima",
    "Rasalgethi",
    "Sadachbia",
    "Sadaltager",
    "Schedar",
    "Sulafat",
    "Umbriel",
    "Vindemiatrix",
    "Zephyr",
    "Zubenelgenubi",
]


@pytest.mark.parametrize("voice", CONTRACT_VOICES)
def test_voice_accepted(voice):
    assert check_voice(voice) is None


@pytest.mark.parametrize(
    "voice",
    ["charon", "CHARON", "callirrhoe", " Charon", "Charon ", "", "kore", "KORE", "Nobody"],
)
def test_voice_rejected(voice):
    assert isinstance(check_voice(voice), Violation)


def test_voices_tuple():
    assert list(VOICES) == CONTRACT_VOICES
    assert len(VOICES) == 30
    assert len(set(VOICES)) == 30


def test_voice_message_and_kind():
    violation = check_voice("Nobody")
    assert violation is not None
    assert violation.rule == "synth-option"
    assert (
        violation.message
        == "voice must be one of the 30 prebuilt voices (see the synth contract)"
    )


@pytest.mark.parametrize("language", ["en-GB", "\u001c", "\u001c "])
def test_language_accepted(language):
    assert check_language(language) is None


@pytest.mark.parametrize("language", ["", " ", "   ", "　"])
def test_language_rejected(language):
    assert isinstance(check_language(language), Violation)


@pytest.mark.parametrize("text", ["Narrate calmly.", "\u001c", "\u001c "])
def test_instruction_accepted(text):
    assert check_instruction(text) is None


@pytest.mark.parametrize("text", ["", " ", "   ", "　", "a\ud800b", "\ud800"])
def test_instruction_rejected(text):
    assert isinstance(check_instruction(text), Violation)


def test_defaults():
    assert DEFAULT_LANGUAGE == "en-GB"
