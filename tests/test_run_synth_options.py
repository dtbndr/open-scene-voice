import io
import json
import sys

import pytest
from wav_helper import wav_audio

from scenevoice.synth import run_synth
from scenevoice.synth.check_instruction import check_instruction
from scenevoice.synth.check_language import check_language

MODULE = "scenevoice.synth.run_preflight"
VOICE_TEXT = "voice must be one of the 30 prebuilt voices (see the synth contract)"
MODEL_TEXT = (
    "model must be one of gemini-3.8-flash-tts, gemini-3.8-flash-lite-tts, eleven_flash_v2_5, eleven_v4"
)
BAD_MODELS = ["", "Gemini-3.8-Flash-TTS", "gemini-3.8-flash-tts ", "gemini-3.1-flash-tts-preview"]
ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": "dummy-key-value",
}
AUDIO = wav_audio()


class Recorder:
    def __init__(self):
        self.factory_calls = 0
        self.models = []
        self.bodies = []
        self.styles = []

    def factory(self, env, model):
        self.factory_calls += 1
        self.models.append(model)

        def provider(request):
            body = request.body
            style = request.instruction
            self.bodies.append(body)
            self.styles.append(style)
            return AUDIO

        return provider


class TtyStdin:
    def __init__(self):
        self.isatty_calls = 0
        self.buffer_reads = 0

    def isatty(self):
        self.isatty_calls += 1
        return True

    @property
    def buffer(self):
        self.buffer_reads += 1
        raise AssertionError("stdin read")


def write_plan(tmp_path):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"scenes": [{"ordinal": 1, "title": "t", "body": "hello"}]}))
    return path


def call(tmp_path, rec, stderr=None, **overrides):
    stderr = stderr if stderr is not None else io.StringIO()
    args = dict(
        plan_path=write_plan(tmp_path),
        stdin=TtyStdin(),
        process_env=ENV,
        dotenv_path=tmp_path / "missing.env",
        out_dir=tmp_path / "out",
        voice="Callirrhoe",
        model="gemini-3.8-flash-tts",
        language="en-GB",
        instruction=None,
        provider_factory=rec.factory,
        stderr=stderr,
    )
    args.update(overrides)
    return run_synth(**args), stderr.getvalue()


@pytest.mark.parametrize(
    "overrides",
    [
        {"voice": "Nobody"},
        {"model": "nope"},
        {"language": "  "},
        {"language": ""},
        {"instruction": ""},
        {"instruction": "　"},
        {"instruction": "bad\ud800"},
    ],
)
def test_bad_option_fails_without_factory_or_provider(tmp_path, capsys, overrides):
    rec = Recorder()
    code, err = call(tmp_path, rec, **overrides)
    assert code == 1
    assert err.startswith("scenevoice synth: FAIL ")
    assert rec.factory_calls == 0 and rec.bodies == []
    assert not (tmp_path / "out").exists()
    assert capsys.readouterr().out == ""


def test_control_character_instruction_is_accepted(tmp_path):
    rec = Recorder()
    code, err = call(tmp_path, rec, instruction="\u001c")
    assert code == 0, err
    assert rec.bodies == ["hello"] and rec.styles == ["\u001c"]


def test_none_instruction_passes_through_as_style_none(tmp_path):
    rec = Recorder()
    code, err = call(tmp_path, rec, instruction=None)
    assert code == 0, err
    assert rec.bodies == ["hello"] and rec.styles == [None]


def test_options_checked_in_order_voice_first(tmp_path):
    rec = Recorder()
    code, err = call(tmp_path, rec, voice="Nobody", language="", instruction="")
    assert code == 1
    assert "voice" in err and "language" not in err and "instruction" not in err


def test_combined_failure_reports_only_voice_and_does_no_io(tmp_path, monkeypatch, capsys):
    reads = []
    mod = sys.modules[MODULE]
    real = mod.resolve_env
    monkeypatch.setattr(mod, "resolve_env", lambda *a: reads.append(a) or real(*a))
    rec = Recorder()
    stdin = TtyStdin()
    out = tmp_path / "out"
    code, err = call(
        tmp_path, rec, voice="Nobody", plan_path=tmp_path / "nope.json", stdin=stdin, out_dir=out
    )
    assert code == 1
    assert err.count("FAIL") == 1 and "voice" in err
    assert "cannot read" not in err and "terminal" not in err
    assert stdin.isatty_calls == 0 and stdin.buffer_reads == 0
    assert reads == [] and not out.exists() and rec.factory_calls == 0
    assert capsys.readouterr().out == ""
    # positive control: with valid options the spy IS reached
    call(tmp_path, rec, plan_path=write_plan(tmp_path))
    assert len(reads) == 1


BAD_OPTIONS = [
    pytest.param({"voice": "Nobody"}, id="voice"),
    pytest.param({"model": "nope"}, id="model"),
    pytest.param({"language": ""}, id="blank-language"),
    pytest.param({"instruction": "　"}, id="blank-instruction"),
]


@pytest.mark.parametrize("bad", BAD_OPTIONS)
def test_bad_option_never_probes_terminal_stdin(tmp_path, capsys, bad):
    rec, stdin, out = Recorder(), TtyStdin(), tmp_path / "out"
    code, err = call(tmp_path, rec, plan_path=None, stdin=stdin, out_dir=out, **bad)
    assert code == 1 and err.count("FAIL") == 1 and "terminal" not in err
    assert stdin.isatty_calls == 0 and stdin.buffer_reads == 0
    assert rec.factory_calls == 0 and not out.exists()
    assert capsys.readouterr().out == ""
    # positive control: valid options DO reach the step-1 terminal probe
    control = TtyStdin()
    code, err = call(tmp_path, rec, plan_path=None, stdin=control)
    assert code == 1 and "terminal" in err
    assert control.isatty_calls == 1 and rec.factory_calls == 0


@pytest.mark.parametrize("bad", BAD_OPTIONS)
def test_bad_option_never_resolves_env_with_valid_plan(tmp_path, monkeypatch, capsys, bad):
    spied = []
    mod = sys.modules[MODULE]
    real = mod.resolve_env
    monkeypatch.setattr(mod, "resolve_env", lambda *a: spied.append(a) or real(*a))
    rec, out = Recorder(), tmp_path / "out"
    code, err = call(tmp_path, rec, out_dir=out, **bad)
    assert code == 1 and err.count("FAIL") == 1
    assert spied == [] and rec.factory_calls == 0 and rec.bodies == []
    assert not out.exists()
    assert capsys.readouterr().out == ""
    # positive control: the same setup with valid options reaches the spied step
    code, err = call(tmp_path, rec, out_dir=out)
    assert code == 0, err
    assert len(spied) == 1 and rec.factory_calls == 1


@pytest.mark.parametrize("model", BAD_MODELS)
def test_bad_model_fails_with_exact_text_and_no_io(tmp_path, monkeypatch, capsys, model):
    reads = []
    mod = sys.modules[MODULE]
    real = mod.resolve_env
    monkeypatch.setattr(mod, "resolve_env", lambda *a: reads.append(a) or real(*a))
    rec, stdin, out = Recorder(), TtyStdin(), tmp_path / "out"
    code, err = call(tmp_path, rec, model=model, plan_path=None, stdin=stdin, out_dir=out)
    assert code == 1
    assert err == f"scenevoice synth: FAIL {MODEL_TEXT}\n"
    assert rec.factory_calls == 0 and rec.bodies == [] and not out.exists()
    assert stdin.isatty_calls == 0 and stdin.buffer_reads == 0 and reads == []
    assert capsys.readouterr().out == ""
    # positive control: a good model reaches the factory, the stdin probe and the env spy
    code, err = call(tmp_path, rec, out_dir=out)
    assert code == 0, err
    assert rec.factory_calls == 1 and len(reads) == 1


def test_bad_voice_reports_the_short_text(tmp_path):
    code, err = call(tmp_path, Recorder(), voice="Nobody")
    assert code == 1
    assert err == f"scenevoice synth: FAIL {VOICE_TEXT}\n"


@pytest.mark.parametrize("model", ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"])
def test_factory_receives_the_model_exactly_once(tmp_path, model):
    rec = Recorder()
    code, err = call(tmp_path, rec, model=model)
    assert code == 0, err
    assert rec.models == [model] and rec.factory_calls == 1


ALL_BAD = {"voice": "Nobody", "model": "nope", "language": "", "instruction": ""}
LANGUAGE_TEXT = check_language("").message
INSTRUCTION_TEXT = check_instruction("").message


@pytest.mark.parametrize(
    "overrides, text",
    [
        pytest.param(ALL_BAD, MODEL_TEXT, id="all-bad-model-wins"),
        pytest.param({**ALL_BAD, "model": "gemini-3.8-flash-tts"}, VOICE_TEXT, id="voice-beats-language"),
        pytest.param(
            {"language": "", "instruction": ""}, LANGUAGE_TEXT, id="language-beats-instruction"
        ),
        pytest.param({"instruction": ""}, INSTRUCTION_TEXT, id="instruction-alone"),
    ],
)
def test_option_check_order_model_voice_language_instruction(tmp_path, overrides, text):
    rec = Recorder()
    code, err = call(tmp_path, rec, **overrides)
    assert code == 1
    assert err == f"scenevoice synth: FAIL {text}\n"
    assert rec.factory_calls == 0 and not (tmp_path / "out").exists()
