import scenevoice.synth as synth
from scenevoice.synth.models import MODELS


def test_models_tuple():
    assert MODELS == (
        "gemini-3.8-flash-tts",
        "gemini-3.8-flash-lite-tts",
        "eleven_flash_v2_5",
        "eleven_v4",
    )


def test_synth_exports_models_and_check_model():
    assert synth.MODELS is MODELS
    assert callable(synth.check_model)
    assert "MODELS" in synth.__all__
    assert "check_model" in synth.__all__
