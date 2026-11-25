"""check_elevenlabs_options owns the wording of both refusals; callers compare against it, not against a copy."""

import io
import json

import pytest

from scenevoice.synth import run_synth
from scenevoice.synth.check_elevenlabs_options import check_elevenlabs_options
from scenevoice.synth.check_instruction import check_instruction
from scenevoice.synth.check_language import check_language
from scenevoice.synth.check_model import check_model
from scenevoice.synth.check_scene import check_scene
from scenevoice.synth.check_voice import check_voice
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


def test_every_prebuilt_voice_is_accepted():
    assert all(check_voice(voice) is None for voice in CONTRACT_VOICES)


@pytest.mark.parametrize("voice", ["charon", "", "Nobody"])
def test_voice_rejected(voice):
    assert isinstance(check_voice(voice), Violation)


def test_voices_tuple():
    assert list(VOICES) == CONTRACT_VOICES


def test_voice_message_and_kind():
    violation = check_voice("Nobody")
    assert violation is not None
    assert violation.rule == "synth-option"
    assert (
        violation.message
        == "voice must be one of the 30 prebuilt voices (see the synth contract)"
    )


def test_language_accepted_and_blank_rejected():
    assert check_language("en-GB") is None
    assert isinstance(check_language("  "), Violation)


def test_instruction_accepted_and_blank_or_unencodable_rejected():
    assert check_instruction("Narrate calmly.") is None
    for text in ("", "   ", "\ud800"):
        assert isinstance(check_instruction(text), Violation)


MODEL_MESSAGE = "model must be one of gemini-3.8-flash-tts, gemini-3.8-flash-lite-tts, eleven_flash_v2_5, eleven_v4"


@pytest.mark.parametrize("scene,count", [(1, 5), (5, 5)])
def test_in_range_scene_passes(scene, count):
    assert check_scene(scene, count) is None


@pytest.mark.parametrize("scene", [0, 6])
def test_out_of_range_scene_is_refused_naming_scene_count(scene):
    violation = check_scene(scene, 5)
    assert isinstance(violation, Violation)
    assert violation.rule == "scene"
    assert violation.message == f"--scene {scene} is out of range (the plan has 5 scenes)"


@pytest.mark.parametrize("model", ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"])
def test_model_accepted(model):
    assert check_model(model) is None


@pytest.mark.parametrize("model", ["", "GEMINI-3.8-FLASH-TTS", "gemini-3.1-flash-tts-preview"])
def test_model_rejected(model):
    violation = check_model(model)
    assert isinstance(violation, Violation)
    assert violation.rule == "synth-option"
    assert violation.message == MODEL_MESSAGE


def test_language_is_refused_with_its_exact_message():
    result = check_elevenlabs_options("en-GB", None)
    assert isinstance(result, Violation)
    assert result.message == "--language is not supported with an ElevenLabs model"


def test_instruction_is_refused_with_its_exact_message_even_when_blank():
    for instruction in ("calm", ""):
        result = check_elevenlabs_options(None, instruction)
        assert isinstance(result, Violation)
        assert result.message == "--instruction is not supported with an ElevenLabs model"


def test_language_is_reported_before_instruction():
    result = check_elevenlabs_options("", "calm")
    assert isinstance(result, Violation)
    assert result.message == "--language is not supported with an ElevenLabs model"


def test_neither_option_passes():
    assert check_elevenlabs_options(None, None) is None


GEMINI_ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": "dummy-key-value",
}


class Stdin:
    def __init__(self):
        self.probed = 0

    def isatty(self):
        self.probed += 1
        return True


def call(tmp_path, **overrides):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"scenes": [{"ordinal": 1, "title": "t", "body": "hello"}]}))
    calls = []
    err = io.StringIO()
    stdin = Stdin()
    args = dict(
        plan_path=plan,
        stdin=stdin,
        process_env={"ELEVENLABS_API_KEY": "k", **GEMINI_ENV},
        dotenv_path=tmp_path / "missing.env",
        out_dir=tmp_path / "out",
        voice="v",
        model="eleven_flash_v2_5",
        language=None,
        instruction=None,
        provider_factory=lambda env, model: calls.append(1),
        stderr=err,
    )
    args.update(overrides)
    code = run_synth(**args)
    assert calls == [] and not (tmp_path / "out").exists() and stdin.probed == 0
    return code, err.getvalue()


def test_elevenlabs_unencodable_voice(tmp_path):
    code, err = call(tmp_path, voice="a\udcffb")
    assert code == 1
    assert err == "scenevoice synth: FAIL voice cannot be encoded as UTF-8\n"


def test_gemini_unencodable_language(tmp_path):
    code, err = call(tmp_path, model="gemini-3.8-flash-tts", voice="Callirrhoe", language="\udcff")
    assert code == 1
    assert err == "scenevoice synth: FAIL language cannot be encoded as UTF-8\n"


def test_gemini_surrogate_voice_gets_the_30_voices_text(tmp_path):
    code, err = call(tmp_path, model="gemini-3.8-flash-tts", voice="\udcff")
    assert err == (
        "scenevoice synth: FAIL voice must be one of the 30 prebuilt voices (see the synth contract)\n"
    )


@pytest.mark.parametrize("voice", ["nope"])
def test_check_voice_none_accepts_any_nonblank_encodable(voice):
    assert check_voice(voice, None) is None
