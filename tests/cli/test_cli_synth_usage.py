import io

import pytest
from cli_usage_helper import reaches_core, run_usage
from paths_helper import REPO_ROOT
from wav_helper import vertex_wav_response

from scenevoice.cli.main import main
from scenevoice.plan import serialize_plan
from scenevoice.synth import ENV_NAMES, MODELS, make_vertex_provider
from scenevoice.validation import load_scenes

VOICE = "Callirrhoe"
MODEL = "gemini-3.8-flash-tts"
LITE = "gemini-3.8-flash-lite-tts"


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


@pytest.mark.parametrize("voice", ["charon", ""])
def test_bad_voice(probes, capsys, voice):
    run_usage(probes, ["plan.json", "--out", str(probes.out), "--voice", voice, "--model", "gemini-3.8-flash-tts"], capsys)


@pytest.mark.parametrize("blank", ["", " "])
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


BAD_MODELS = ["", "gemini-3.8-flash-tts-x"]


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


def test_empty_model_equals_form_is_left_to_argparse(probes, capsys):
    captured = run_usage(
        probes, ["plan.json", "--out", str(probes.out), "--voice", VOICE, "--model="], capsys)
    assert len(error_lines(captured)) == 1


@pytest.mark.parametrize(
    "extra",
    [
        # U+001C..U+001F are not blank under the WS8 rule: the core sees them, argparse never does.
        ["--voice", VOICE, "--instruction=\x1c\x1d\x1e\x1f"],
        # a valid voice beyond the original two, with a valid model
        ["--voice", "Puck"],
    ],
)
def test_valid_values_are_not_a_usage_error(probes, capsys, extra):
    reaches_core(probes, ["plan.json", "--out", str(probes.out), "--model", MODEL, *extra], capsys)


@pytest.mark.parametrize(
    "options",
    [
        ["--voice", "nope", "--model", "bad-model"],
        ["--model", "bad-model", "--voice", "nope"],
    ],
    ids=["voice-first", "model-first"],
)
def test_bad_model_wins_over_bad_voice_in_either_order(probes, capsys, options):
    # --voice has no argparse choices: a bad voice is the post-parse step's, after argparse
    captured = run_usage(probes, ["plan.json", "--out", str(probes.out), *options], capsys)
    assert len(error_lines(captured)) == 1
    tail = error_text(captured)
    assert "--model" in tail and "--voice" not in tail


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
    script = REPO_ROOT / "sample/scripts/short.md"
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
