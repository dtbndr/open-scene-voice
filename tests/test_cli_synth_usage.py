import io
from pathlib import Path

import pytest
from wav_helper import vertex_wav_response

from scenevoice.cli.main import main
from scenevoice.plan import serialize_plan
from scenevoice.synth import ENV_NAMES, MODELS, VOICES, make_vertex_provider
from scenevoice.validation import load_scenes

VOICE = "Callirrhoe"
MODEL = "gemini-3.8-flash-tts"
LITE = "gemini-3.8-flash-lite-tts"


class FailingStdin:
    def __init__(self):
        self.touched = []

    @property
    def buffer(self):
        self.touched.append("buffer")
        raise AssertionError("stdin was read")

    def isatty(self):
        self.touched.append("isatty")
        raise AssertionError("stdin was probed")

    def read(self, *args):
        self.touched.append("read")
        raise AssertionError("stdin was read")


@pytest.fixture
def probes(tmp_path, monkeypatch):
    """Isolated cwd with a plan and .env; records every file open and factory call."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "plan.json").write_text('{"scenes": []}')
    (tmp_path / ".env").write_text("GOOGLE_CLOUD_PROJECT=p\n")
    stdin = FailingStdin()
    monkeypatch.setattr("sys.stdin", stdin)
    opened = []
    real_open = io.open

    def spy_open(file, *args, **kwargs):
        opened.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(io, "open", spy_open)
    factory_calls = []

    def factory(env, model):
        factory_calls.append(env)
        raise AssertionError("factory called")

    class Probes:
        pass

    p = Probes()
    p.stdin, p.opened, p.factory_calls, p.factory, p.out = (
        stdin, opened, factory_calls, factory, tmp_path / "out")
    return p


def run_usage(probes, argv, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["synth", *argv], provider_factory=probes.factory)
    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert captured.out == ""
    assert probes.stdin.touched == []
    assert probes.factory_calls == []
    assert not [f for f in probes.opened if f.endswith((".env", "plan.json"))]
    assert not probes.out.exists()
    return captured


def error_lines(captured):
    return [ln for ln in captured.err.splitlines() if "error:" in ln]


def error_text(captured):
    """Only what follows the `error:` marker (argparse's usage line lists every name)."""
    return captured.err.split("error:", 1)[1]


def test_spy_positive_control_sees_opens(probes):
    with io.open(".env"):  # noqa: UP020 (the spy patches io.open)
        pass
    assert probes.opened == [".env"]
    with pytest.raises(AssertionError):
        probes.stdin.isatty()
    with pytest.raises(AssertionError):
        probes.factory({}, "gemini-3.8-flash-tts")


def test_missing_out(probes, capsys):
    run_usage(probes, ["plan.json", "--voice", VOICE, "--model", "gemini-3.8-flash-tts"], capsys)


def test_missing_voice(probes, capsys):
    run_usage(probes, ["plan.json", "--out", str(probes.out), "--model", "gemini-3.8-flash-tts"], capsys)


@pytest.mark.parametrize("voice", ["charon", "Other", "callirrhoe", ""])
def test_bad_voice(probes, capsys, voice):
    run_usage(probes, ["plan.json", "--out", str(probes.out), "--voice", voice, "--model", "gemini-3.8-flash-tts"], capsys)


@pytest.mark.parametrize("blank", ["", " ", "  \t\n", "  　"])
def test_blank_instruction(probes, capsys, blank):
    run_usage(
        probes,
        ["plan.json", "--out", str(probes.out), "--voice", VOICE, "--model", "gemini-3.8-flash-tts", f"--instruction={blank}"],
        capsys,
    )


@pytest.mark.parametrize("blank", ["", " ", "  "])
def test_blank_language(probes, capsys, blank):
    run_usage(
        probes,
        ["plan.json", "--out", str(probes.out), "--voice", VOICE, "--model", "gemini-3.8-flash-tts", f"--language={blank}"],
        capsys,
    )


def test_control_chars_only_instruction_is_not_a_usage_error(probes, capsys):
    # U+001C..U+001F are not blank under the WS8 rule: it reaches the core (exit 1 here
    # because the stdin/factory fakes fail), never argparse's exit 2.
    argv = ["synth", "plan.json", "--out", str(probes.out), "--voice", VOICE, "--model", "gemini-3.8-flash-tts",
            "--instruction=\x1c\x1d\x1e\x1f"]
    try:
        code = main(argv, provider_factory=probes.factory)
    except SystemExit as exc:
        code = exc.code
    assert code == 1
    assert capsys.readouterr().out == ""


BAD_MODELS = ["", "gemini-3.8-flash-tts-x", "Gemini-3.8-Flash-TTS", "gemini-3.1-flash-tts-preview"]


def test_missing_model(probes, capsys):
    captured = run_usage(probes, ["plan.json", "--out", str(probes.out), "--voice", VOICE], capsys)
    assert len(error_lines(captured)) == 1
    assert "--model" in error_text(captured) and "required" in error_text(captured)


@pytest.mark.parametrize("model", BAD_MODELS)
def test_bad_model_names_all_four_models(probes, capsys, model):
    captured = run_usage(
        probes, ["plan.json", "--out", str(probes.out), "--voice", VOICE, "--model", model], capsys)
    assert len(error_lines(captured)) == 1
    assert all(name in error_text(captured) for name in MODELS) and len(MODELS) == 4


def test_bad_voice_names_all_30_voices(probes, capsys):
    captured = run_usage(
        probes, ["plan.json", "--out", str(probes.out), "--voice", "nope", "--model", MODEL], capsys)
    assert len(VOICES) == 30
    assert all(name in error_text(captured) for name in VOICES)


def test_empty_model_equals_form_is_left_to_argparse(probes, capsys):
    captured = run_usage(
        probes, ["plan.json", "--out", str(probes.out), "--voice", VOICE, "--model="], capsys)
    assert len(error_lines(captured)) == 1


def test_valid_voice_beyond_the_original_two_is_not_a_usage_error(probes, capsys):
    # Puck + valid model passes argparse and reaches the core (exit 1: stdin/factory fakes fail).
    try:
        code = main(
            ["synth", "plan.json", "--out", str(probes.out), "--voice", "Puck", "--model", MODEL],
            provider_factory=probes.factory,
        )
    except SystemExit as exc:
        code = exc.code
    assert code == 1
    assert capsys.readouterr().out == ""


def test_bad_model_before_bad_voice_reports_only_the_model(probes, capsys):
    # --voice has no argparse choices any more: a bad voice is the post-parse step's, after argparse
    captured = run_usage(
        probes,
        ["plan.json", "--out", str(probes.out), "--voice", "nope", "--model", "bad-model"], capsys)
    assert len(error_lines(captured)) == 1
    tail = error_text(captured)
    assert "--model" in tail and "--voice" not in tail


def test_model_error_first_reports_only_the_model(probes, capsys):
    captured = run_usage(
        probes,
        ["plan.json", "--out", str(probes.out), "--model", "bad-model", "--voice", "nope"], capsys)
    assert len(error_lines(captured)) == 1
    assert "--model" in captured.err.split("error:")[1]
    assert "--voice" not in captured.err.split("error:")[1]


def test_bad_value_wins_over_a_missing_option(probes, capsys):
    captured = run_usage(
        probes, ["plan.json", "--out", str(probes.out), "--voice", VOICE, "--language="], capsys)  # no --model
    assert len(error_lines(captured)) == 1
    tail = error_text(captured)
    assert "--language" in tail and "must not be blank" in tail and "required" not in tail


def test_two_missing_required_options_report_one_error(probes, capsys):
    captured = run_usage(probes, ["plan.json", "--out", str(probes.out)], capsys)
    assert len(error_lines(captured)) == 1


def test_repeated_model_last_occurrence_wins(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    for name in ENV_NAMES:
        monkeypatch.setenv(name, "dummy-value")
    script = Path(__file__).resolve().parent.parent / "sample/scripts/short.md"
    (tmp_path / "plan.json").write_bytes(serialize_plan(load_scenes(script.read_bytes())).encode("utf-8"))
    posts = []

    def post(url, headers, body, timeout):
        posts.append(url)
        return vertex_wav_response()

    code = main(
        ["synth", "plan.json", "--out", str(tmp_path / "out"), "--voice", VOICE,
         "--model", MODEL, "--model", LITE],
        provider_factory=lambda env, model: make_vertex_provider(env, model, post=post),
    )
    err = capsys.readouterr().err
    assert posts  # positive control: the fake post was reached
    assert code == 0, err
    assert len(set(posts)) == 1  # one URL for every scene
    assert LITE + ":generateContent" in posts[0] and MODEL + ":" not in posts[0]


def test_synth_help_lists_models_and_voices(capsys):
    with pytest.raises(SystemExit):
        main(["synth", "--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert all(name in out for name in (*MODELS, *VOICES))
    assert "TTS model (required, no default)" in out
    assert "exact match" in out and "30 prebuilt" in out


def test_synth_help_mentions_out_and_voice(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["synth", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--out" in out and "--voice" in out and "--model" in out


def test_synth_help_says_instruction_has_no_default(capsys):
    with pytest.raises(SystemExit):
        main(["synth", "--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert "standing instruction" not in out
    assert "no default" in out
    assert "--instruction=TEXT" in out
