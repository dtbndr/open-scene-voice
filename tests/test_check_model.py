import pytest

from scenevoice.synth.check_model import check_model
from scenevoice.validation import Violation


@pytest.mark.parametrize("model", ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"])
def test_model_accepted(model):
    assert check_model(model) is None


@pytest.mark.parametrize(
    "model",
    [
        "",
        "GEMINI-3.8-FLASH-TTS",
        "Gemini-3.8-Flash-Lite-TTS",
        " gemini-3.8-flash-tts",
        "gemini-3.8-flash-tts ",
        "gemini-3.1-flash-tts-preview",
        "gemini-3.8-flash-tts-lite",
    ],
)
def test_model_rejected(model):
    violation = check_model(model)
    assert isinstance(violation, Violation)
    assert violation.rule == "synth-option"
    assert (
        violation.message
        == "model must be one of gemini-3.8-flash-tts, gemini-3.8-flash-lite-tts, eleven_flash_v2_5, eleven_v4"
    )
