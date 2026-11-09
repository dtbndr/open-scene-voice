import io
import json

import pytest
from wav_helper import wav_audio

from scenevoice.synth import run_synth

EL_ENV = {"ELEVENLABS_API_KEY": "dummy-eleven-key"}
GEMINI_ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": "dummy-key-value",
}
FLASH = "eleven_flash_v2_5"
V4 = "eleven_v4"
GEMINI = "gemini-3.8-flash-tts"
MODEL_TEXT = (
    "model must be one of gemini-3.8-flash-tts, gemini-3.8-flash-lite-tts, eleven_flash_v2_5, eleven_v4"
)
LANG_TEXT = "--language is not supported with an ElevenLabs model"
INSTR_TEXT = "--instruction is not supported with an ElevenLabs model"
VOICE_ID = "EXAVITQu4vr4xnSDxMaL"


class Stdin:
    def __init__(self):
        self.probed = 0

    def isatty(self):
        self.probed += 1
        return True


class Rec:
    def __init__(self):
        self.factory_calls = 0
        self.requests = []

    def factory(self, env, model):
        self.factory_calls += 1

        def provider(request):
            self.requests.append(request)
            return wav_audio()

        return provider


def call(tmp_path, rec=None, body="hello", stdin=None, **overrides):
    rec = rec or Rec()
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"scenes": [{"ordinal": 1, "title": "t", "body": body}]}))
    err = io.StringIO()
    args = dict(
        plan_path=plan,
        stdin=stdin or Stdin(),
        process_env=EL_ENV,
        dotenv_path=tmp_path / "missing.env",
        out_dir=tmp_path / "out",
        voice=VOICE_ID,
        model=FLASH,
        language=None,
        instruction=None,
        provider_factory=rec.factory,
        stderr=err,
    )
    args.update(overrides)
    return run_synth(**args), err.getvalue(), rec


def assert_fails(tmp_path, text, **overrides):
    stdin = Stdin()
    code, err, rec = call(tmp_path, stdin=stdin, **overrides)
    assert code == 1
    assert err == f"scenevoice synth: FAIL {text}\n"
    assert rec.factory_calls == 0 and not (tmp_path / "out").exists()
    assert stdin.probed == 0


def test_all_bad_gemini_call_reports_the_model(tmp_path):
    assert_fails(tmp_path, MODEL_TEXT, voice="Nobody", model="nope", language="", instruction="")


def test_bad_voice_with_valid_model_reports_the_voice(tmp_path):
    assert_fails(
        tmp_path,
        "voice must be one of the 30 prebuilt voices (see the synth contract)",
        voice="Nobody", model=GEMINI, process_env=GEMINI_ENV, language="",
    )  # fmt: skip


@pytest.mark.parametrize("voice", ["", "   ", "　"])
def test_elevenlabs_blank_voice(tmp_path, voice):
    assert_fails(tmp_path, "voice must not be blank", voice=voice)


@pytest.mark.parametrize("language", ["en-GB", ""])
def test_elevenlabs_language_not_supported(tmp_path, language):
    assert_fails(tmp_path, LANG_TEXT, language=language)


@pytest.mark.parametrize("instruction", ["calm", ""])
def test_elevenlabs_instruction_not_supported(tmp_path, instruction):
    assert_fails(tmp_path, INSTR_TEXT, instruction=instruction)


def test_elevenlabs_language_beats_instruction(tmp_path):
    assert_fails(tmp_path, LANG_TEXT, language="en-GB", instruction="calm")


def test_elevenlabs_voice_beats_language(tmp_path):
    assert_fails(tmp_path, "voice must not be blank", voice=" ", language="en-GB")


@pytest.mark.parametrize("voice", [VOICE_ID, "nope", "Charon"])
def test_any_voice_id_string_passes(tmp_path, voice):
    code, err, rec = call(tmp_path, voice=voice)
    assert code == 0, err
    assert rec.requests[0].voice == voice


def test_gemini_default_language_resolves_to_en_gb(tmp_path):
    code, err, rec = call(
        tmp_path, voice="Callirrhoe", model=GEMINI, process_env=GEMINI_ENV, language=None
    )  # fmt: skip
    assert code == 0, err
    assert rec.requests[0].language == "en-GB"
    entry = json.loads((tmp_path / "out" / "synth_record.json").read_text())["scenes"][0]
    assert entry["language"] == "en-GB"


def test_elevenlabs_request_and_record_carry_no_language_or_instruction(tmp_path):
    code, err, rec = call(tmp_path)
    assert code == 0, err
    assert rec.requests[0].language is None and rec.requests[0].instruction is None
    entry = json.loads((tmp_path / "out" / "synth_record.json").read_text())["scenes"][0]
    assert entry["language"] is None and entry["instruction"] is None


def test_over_limit_body_fails_before_the_environment_check(tmp_path):
    code, err, rec = call(tmp_path, body="x" * 10001, model=V4, process_env={})
    assert code == 1
    assert err == "scenevoice synth: FAIL body over 10000 characters: scene 1: 10001 characters\n"
    assert rec.factory_calls == 0
