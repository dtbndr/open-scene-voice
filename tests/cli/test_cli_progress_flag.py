"""`--progress` wiring through `main()`, one parametrized test per behaviour, one row per command.

Stderr contract: with `--progress json` every stderr line is a JSON object. Lines that are
not JSON are raw text, for example argparse usage errors, which stay plain text.
"""

import json
import shutil
import sys
from pathlib import Path

import pytest
from align_run_helper import Fake, body
from beats_run_helper import replying
from wav_helper import make_wav

from scenevoice.cli.main import main
from scenevoice.synth import ProviderAudio


def _synth_argv(script):
    plan = Path(script).with_name("plan.json")
    plan.write_text(json.dumps({"scenes": [{"ordinal": 1, "title": "A", "body": "hello"}]}))
    return [
        "synth", str(plan), "--out", "out", "--voice", "Callirrhoe",
        "--model", "gemini-3.8-flash-tts",
    ]


def _pack_argv(script):
    root = Path(script).parent
    plan = root / "pack_plan.json"
    plan.write_text(json.dumps({"scenes": [{"ordinal": 1, "title": "A", "body": "hello"}]}))
    (root / "packed" / "audio").mkdir(parents=True, exist_ok=True)
    (root / "packed" / "audio" / "001.wav").write_bytes(make_wav())
    return ["pack", str(plan), str(root / "packed")]


def _align_argv(script):
    root = Path(script).parent
    plan = root / "align_plan.json"
    plan.write_text(json.dumps({"scenes": [{"ordinal": 1, "title": "A", "body": "hello"}]}))
    (root / "aligned" / "audio").mkdir(parents=True, exist_ok=True)
    (root / "aligned" / "audio" / "001.wav").write_bytes(make_wav(1001))
    return ["align", str(plan), str(root / "aligned")]


def _beats_argv(script):
    return ["beats", script, "--model", "synthetic/model", "--out", str(Path(script).with_name("beats.json"))]


# command name -> argv builder given a script path (rows are added per command)
COMMANDS = {
    "plan": lambda script: ["plan", script], "synth": _synth_argv,
    "pack": _pack_argv,
    "align": _align_argv,
    "beats": _beats_argv,
}


@pytest.fixture(autouse=True)
def fake_synth_provider(clean_env, monkeypatch):
    """No provider call: main() builds its provider through a fake; a key and project are set."""
    for name, value in (
        ("GOOGLE_CLOUD_PROJECT", "proj"),
        ("GOOGLE_CLOUD_LOCATION", "loc"),
        ("VERTEX_AUTHORIZATION_KEY", "k"),
    ):
        monkeypatch.setenv(name, value)
    def factory(env, model):
        return lambda request: ProviderAudio("audio/wav", make_wav())

    cli_main = sys.modules["scenevoice.cli.main"]
    real_command = cli_main.run_synth_command

    def fresh_out(args, provider_factory):  # the same argv runs twice: start each run on an empty --out
        shutil.rmtree(args.out, ignore_errors=True)
        return real_command(args, provider_factory)

    real_pack = cli_main.run_pack_command

    def fresh_pack(args):  # the same argv runs twice: drop the manifest the last run wrote
        Path(args.dir, "scene_manifest.csv").unlink(missing_ok=True)
        return real_pack(args)

    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy-key-value")
    transcript = body([(" hello", 0.1)])  # faked transcriber: no OpenRouter call
    monkeypatch.setattr(cli_main, "make_openrouter_transcriber", lambda key: Fake([transcript] * 9))
    reply = {"scenes": [{"scene": 1, "beats": [{"first": 1, "last": 1, "note": "wide"}]}]}
    monkeypatch.setattr(cli_main, "make_openrouter_chat", replying(reply).factory)  # no OpenRouter call
    real_beats = cli_main.run_beats_command

    def fresh_beats(args, chat_factory):  # the same argv runs twice: beats never overwrites its --out
        Path(args.out).unlink(missing_ok=True)
        return real_beats(args, chat_factory)

    monkeypatch.setattr(cli_main, "run_beats_command", fresh_beats)
    monkeypatch.setattr(cli_main, "run_pack_command", fresh_pack)
    monkeypatch.setattr(cli_main, "make_provider", factory)
    monkeypatch.setattr(cli_main, "run_synth_command", fresh_out)


@pytest.fixture
def script(clean_env):
    path = clean_env / "s.md"
    path.write_text("## A\nhello\n", encoding="utf-8")
    return str(path)


@pytest.mark.parametrize("command", COMMANDS)
def test_default_and_text_have_identical_stderr(command, script, capfd):
    argv = COMMANDS[command](script)
    assert main(argv) == 0
    default_err = capfd.readouterr().err
    assert main([*argv, "--progress", "text"]) == 0
    assert capfd.readouterr().err == default_err


@pytest.mark.parametrize("command", COMMANDS)
def test_json_makes_every_stderr_line_a_json_object(command, script, capfd):
    assert main([*COMMANDS[command](script), "--progress", "json"]) == 0
    lines = capfd.readouterr().err.splitlines()
    assert lines
    for line in lines:
        assert json.loads(line)["command"] == command


@pytest.mark.parametrize("command", COMMANDS)
def test_invalid_mode_is_an_argparse_error(command, script, capfd):
    with pytest.raises(SystemExit) as exc:
        main([*COMMANDS[command](script), "--progress", "xml"])
    assert exc.value.code == 2
    err = capfd.readouterr().err
    assert "invalid choice" in err and not err.lstrip().startswith("{")


@pytest.mark.parametrize("command", COMMANDS)
def test_command_help_mentions_the_flag(command, clean_env, capfd):
    with pytest.raises(SystemExit) as exc:
        main([command, "--help"])
    assert exc.value.code == 0
    assert "--progress" in capfd.readouterr().out


def test_keys_does_not_accept_the_flag(clean_env, capfd):
    with pytest.raises(SystemExit) as exc:
        main(["keys", "status", "--progress", "json"])
    assert exc.value.code == 2


def test_plan_help_names_json_lines_on_stderr(clean_env, capfd):
    with pytest.raises(SystemExit):
        main(["plan", "--help"])
    out = " ".join(capfd.readouterr().out.split())
    assert "JSON lines on stderr" in out
    assert "stdout" not in out
