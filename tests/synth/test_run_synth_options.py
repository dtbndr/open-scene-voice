"""run_synth options: checked in order before any I/O, per provider; valid ones reach the provider unchanged."""

import io
import json
import sys

import pytest
from wav_helper import wav_audio

from scenevoice.synth import run_synth
from scenevoice.synth.check_elevenlabs_options import check_elevenlabs_options
from scenevoice.synth.check_instruction import check_instruction
from scenevoice.synth.check_model import check_model

PREFIX = "scenevoice synth: FAIL "
GEMINI, LITE = "gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"
FLASH, V4 = "eleven_flash_v2_5", "eleven_v4"
VOICE_ID = "EXAVITQu4vr4xnSDxMaL"
GEMINI_ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": "dummy-key-value",
}
EL = {"process_env": {"ELEVENLABS_API_KEY": "dummy-eleven-key"}, "voice": VOICE_ID, "model": FLASH, "language": None}
MODEL_TEXT = check_model("nope").message
INSTRUCTION_TEXT = check_instruction("").message
EL_LANGUAGE_TEXT = check_elevenlabs_options("en-GB", None).message
ALL_BAD = {"voice": "Nobody", "model": "nope", "language": "", "instruction": ""}


class Recorder:
    def __init__(self):
        self.factory_calls = 0
        self.models = []
        self.requests = []

    def factory(self, env, model):
        self.factory_calls += 1
        self.models.append(model)

        def provider(request):
            self.requests.append(request)
            return wav_audio()

        return provider


class TtyStdin:
    def __init__(self):
        self.isatty_calls = 0

    def isatty(self):
        self.isatty_calls += 1
        return True


def call(tmp_path, rec, body="hello", plan=True, **overrides):
    path = None
    if plan:
        path = tmp_path / "plan.json"
        path.write_text(json.dumps({"scenes": [{"ordinal": 1, "title": "t", "body": body}]}))
    stderr = io.StringIO()
    args = dict(
        plan_path=path,
        stdin=TtyStdin(),
        process_env=GEMINI_ENV,
        dotenv_path=tmp_path / "missing.env",
        out_dir=tmp_path / "out",
        voice="Callirrhoe",
        model=GEMINI,
        language="en-GB",
        instruction=None,
        provider_factory=rec.factory,
        stderr=stderr,
    )
    args.update(overrides)
    return run_synth(**args), stderr.getvalue()


@pytest.fixture
def env_reads(monkeypatch):
    reads = []
    module = sys.modules["scenevoice.synth.run_preflight"]
    real = module.resolve_env
    monkeypatch.setattr(module, "resolve_env", lambda *a, **k: reads.append(a) or real(*a, **k))
    return reads


def assert_refused_without_io(tmp_path, capsys, rec, stdin, env_reads, code, err, text):
    assert code == 1
    assert err == PREFIX + text + "\n"
    assert rec.factory_calls == 0 and rec.requests == []
    assert stdin.isatty_calls == 0 and env_reads == [] and not (tmp_path / "out").exists()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "overrides, text",
    [
        pytest.param(ALL_BAD, MODEL_TEXT, id="all-bad-model-wins"),
        pytest.param({"instruction": ""}, INSTRUCTION_TEXT, id="instruction-alone"),
        pytest.param({**EL, "language": "en-GB", "instruction": "calm"}, EL_LANGUAGE_TEXT, id="el-language-beats-instruction"),
    ],
)
def test_options_are_checked_in_order_before_any_io(tmp_path, capsys, env_reads, overrides, text):
    rec, stdin = Recorder(), TtyStdin()
    code, err = call(tmp_path, rec, plan=False, stdin=stdin, **overrides)
    assert_refused_without_io(tmp_path, capsys, rec, stdin, env_reads, code, err, text)


def test_valid_options_do_reach_the_stdin_probe_and_the_factory(tmp_path, env_reads):
    rec, stdin = Recorder(), TtyStdin()
    code, err = call(tmp_path, rec, plan=False, stdin=stdin)
    assert code == 1 and "terminal" in err and stdin.isatty_calls == 1 and rec.factory_calls == 0
    code, err = call(tmp_path, rec)
    assert code == 0, err
    assert rec.factory_calls == 1 and len(env_reads) == 1


@pytest.mark.parametrize("model", [GEMINI, LITE])
def test_factory_gets_the_model_once_and_any_listed_voice_runs(tmp_path, model):
    rec = Recorder()
    code, err = call(tmp_path, rec, model=model, voice="Zubenelgenubi")
    assert code == 0, err
    assert rec.models == [model] and rec.factory_calls == 1
    assert [r.voice for r in rec.requests] == ["Zubenelgenubi"]


@pytest.mark.parametrize(
    "style", [None, "  padded é中\U0001f600  "], ids=["none", "padded-unicode"],
)
def test_style_reaches_the_provider_unmodified(tmp_path, style):
    rec = Recorder()
    code, err = call(tmp_path, rec, instruction=style)
    assert code == 0, err
    assert [r.instruction for r in rec.requests] == [style]
    assert [r.body for r in rec.requests] == ["hello"]


@pytest.mark.parametrize("voice", [VOICE_ID, "Charon"])
def test_elevenlabs_accepts_any_voice_id_and_records_no_language_or_instruction(tmp_path, voice):
    rec = Recorder()
    code, err = call(tmp_path, rec, **{**EL, "voice": voice})
    assert code == 0, err
    request = rec.requests[0]
    assert request.voice == voice and request.language is None and request.instruction is None
    entry = json.loads((tmp_path / "out" / "synth_record.json").read_text())["scenes"][0]
    assert entry["language"] is None and entry["instruction"] is None


def test_gemini_default_language_resolves_to_en_gb_in_request_and_record(tmp_path):
    rec = Recorder()
    code, err = call(tmp_path, rec, language=None)
    assert code == 0, err
    assert rec.requests[0].language == "en-GB"
    entry = json.loads((tmp_path / "out" / "synth_record.json").read_text())["scenes"][0]
    assert entry["language"] == "en-GB"


def test_elevenlabs_body_limit_is_checked_before_the_keys(tmp_path):
    rec = Recorder()
    code, err = call(tmp_path, rec, body="x" * 10001, **{**EL, "model": V4, "process_env": {}})
    assert code == 1 and err.startswith(PREFIX + "body over 10000 characters")
    assert rec.factory_calls == 0
