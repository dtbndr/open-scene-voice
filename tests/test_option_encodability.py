import io
import json

import pytest

from scenevoice.synth import run_synth
from scenevoice.synth.check_voice import check_voice

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


def test_blank_value_gets_the_blank_text_first(tmp_path):
    code, err = call(tmp_path, voice="　")
    assert err == "scenevoice synth: FAIL voice must not be blank\n"
    code, err = call(tmp_path, model="gemini-3.8-flash-tts", voice="Callirrhoe", language="  ")
    assert err == "scenevoice synth: FAIL language must not be blank\n"


def test_gemini_surrogate_voice_gets_the_30_voices_text(tmp_path):
    code, err = call(tmp_path, model="gemini-3.8-flash-tts", voice="\udcff")
    assert err == (
        "scenevoice synth: FAIL voice must be one of the 30 prebuilt voices (see the synth contract)\n"
    )


def test_check_voice_default_keeps_gemini_behaviour():
    assert check_voice("Callirrhoe") is None
    assert check_voice("nope") is not None


@pytest.mark.parametrize("voice", ["Callirrhoe", "nope"])
def test_check_voice_none_accepts_any_nonblank_encodable(voice):
    assert check_voice(voice, None) is None
