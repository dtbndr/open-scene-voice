import pytest
from cli_usage_helper import reaches_core, run_usage

from scenevoice.synth import MODELS, VOICES

FLASH = "eleven_flash_v2_5"
GEMINI = "gemini-3.8-flash-tts"
VOICE_ID = "EXAVITQu4vr4xnSDxMaL"


def error_line(captured):
    lines = [ln for ln in captured.err.splitlines() if "error:" in ln]
    assert len(lines) == 1
    assert captured.err.splitlines()[0].startswith("usage: scenevoice synth")
    return lines[0]


def argv(probes, *extra):
    return ["plan.json", "--out", str(probes.out), *extra]


def test_blank_elevenlabs_voice(probes, capsys):
    captured = run_usage(probes, argv(probes, "--model", FLASH, "--voice", " "), capsys)
    assert error_line(captured) == "scenevoice synth: error: argument --voice: must not be blank"


@pytest.mark.parametrize("form", [["--language", "en-GB"], ["--language=fr-FR"]])
def test_language_not_supported_with_elevenlabs(probes, capsys, form):
    captured = run_usage(probes, argv(probes, "--model", FLASH, "--voice", VOICE_ID, *form), capsys)
    assert error_line(captured) == (
        "scenevoice synth: error: argument --language: not supported with an ElevenLabs model")


def test_instruction_not_supported_with_elevenlabs(probes, capsys):
    captured = run_usage(
        probes, argv(probes, "--model", FLASH, "--voice", VOICE_ID, "--instruction", "calm"), capsys)
    assert error_line(captured) == (
        "scenevoice synth: error: argument --instruction: not supported with an ElevenLabs model")


def test_voice_beats_language_beats_instruction(probes, capsys):
    base = argv(probes, "--model", FLASH)
    captured = run_usage(
        probes, [*base, "--voice", " ", "--language", "en-GB", "--instruction", "calm"], capsys)
    assert error_line(captured).endswith("argument --voice: must not be blank")
    captured = run_usage(
        probes, [*base, "--voice", VOICE_ID, "--language", "en-GB", "--instruction", "calm"], capsys)
    assert error_line(captured).endswith("argument --language: not supported with an ElevenLabs model")


def test_blank_language_with_elevenlabs_is_left_to_argparse(probes, capsys):
    captured = run_usage(
        probes, argv(probes, "--model", FLASH, "--voice", VOICE_ID, "--language="), capsys)
    assert error_line(captured) == "scenevoice synth: error: argument --language: must not be blank"


@pytest.mark.parametrize("model", ["eleven_v3", "eleven_multilingual_v2"])
def test_other_elevenlabs_models_are_invalid_choices(probes, capsys, model):
    captured = run_usage(probes, argv(probes, "--model", model, "--voice", VOICE_ID), capsys)
    line = error_line(captured)
    assert "invalid choice" in line and all(name in line for name in MODELS) and len(MODELS) == 4


def test_gemini_bad_voice_line_is_byte_identical_to_argparse_choices(probes, capsys):
    captured = run_usage(probes, argv(probes, "--model", GEMINI, "--voice", "nope"), capsys)
    assert error_line(captured) == (
        "scenevoice synth: error: argument --voice: invalid choice: 'nope' "
        f"(choose from {', '.join(VOICES)})")


def test_missing_model_beats_a_bad_voice(probes, capsys):
    captured = run_usage(probes, argv(probes, "--voice", "nope"), capsys)
    line = error_line(captured)
    assert "--model" in line and "required" in line and "--voice" not in line


def test_valid_voice_id_without_language_passes_the_post_parse_step(probes, capsys):
    reaches_core(probes, argv(probes, "--model", FLASH, "--voice", VOICE_ID), capsys)
