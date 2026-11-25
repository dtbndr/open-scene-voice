"""`scenevoice beats` wiring through `main` with an injected chat factory (no network, no real .env)."""

import logging
import os
import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values

import scenevoice.cli.beats as beats_command
import scenevoice.cli.main as cli_main
from scenevoice.cli.main import main

SCRIPT = "## A\nHello there.\n"


pytestmark = pytest.mark.usefixtures("no_sockets")


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    (tmp_path / "s.md").write_text(SCRIPT, encoding="utf-8")


@pytest.fixture
def spy(monkeypatch):
    class Calls(list):
        kwargs: list = []

    calls = Calls()
    kwarg_calls = calls.kwargs = []

    def fake_run_beats(*args, **kwargs):
        calls.append(args)
        kwarg_calls.append(kwargs)
        return 7

    monkeypatch.setattr(beats_command, "run_beats", fake_run_beats)
    return calls


def test_main_returns_what_run_beats_returns_and_passes_arguments(spy):
    sentinel = object()

    def factory(key):
        return sentinel

    code = main(["beats", "s.md", "--model", "some/model", "--out", "b.json"], beats_factory=factory)
    assert code == 7
    (script, out, model, env, dotenv, chat_factory, err, out_stream), = spy
    assert (script, out, model) == ("s.md", "b.json", "some/model")
    assert str(dotenv) == ".env"
    assert chat_factory is factory
    assert err is sys.stderr and out_stream is sys.stdout
    assert env is os.environ


def test_key_file_path_from_the_environment_is_passed_to_run_beats(spy):
    assert main(["beats", "s.md", "--model", "m", "--out", "b.json"]) == 7
    assert spy.kwargs == [
        {"key_file_path": Path(os.environ["SCENEVOICE_KEYS_FILE"]), "progress_mode": "text"}
    ]


def test_omitted_factory_falls_back_to_make_openrouter_chat(spy, monkeypatch):
    marker = object()
    monkeypatch.setattr(cli_main, "make_openrouter_chat", marker)
    assert main(["beats", "s.md", "--model", "m", "--out", "b.json"]) == 7
    assert spy[0][5] is marker


@pytest.mark.parametrize(
    "argv",
    [
        ["--model", "m", "--out", "b.json"],
        ["s.md", "--out", "b.json"],
        ["s.md", "--model", "m"],
        ["s.md", "--model", "", "--out", "b.json"],
    ],
)
def test_usage_errors_exit_2_before_run_beats(argv, spy):
    with pytest.raises(SystemExit) as exit_info:
        main(["beats", *argv])
    assert exit_info.value.code == 2
    assert spy == []


FAILED_REPLY_SENTENCE = (
    "If the reply fails its checks or is cut off at the length limit, it is saved as raw text, "
    "the command exits 1, and the file is not usable beats. A paid call is used either way."
)


@pytest.fixture
def dotenv_logger():
    logger = logging.getLogger("dotenv.main")
    saved = (logger.disabled, logger.level)
    logger.disabled = False
    logger.setLevel(logging.NOTSET)
    yield logger
    logger.disabled, level = saved
    logger.setLevel(level)


MALFORMED_ENV = "this is not valid = = =\nSECRET garbage line\n"


def test_positive_control_dotenv_warns_when_its_logger_is_not_disabled(tmp_path, caplog, dotenv_logger):
    (tmp_path / ".env").write_text(MALFORMED_ENV, encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="dotenv.main"):
        dotenv_values(tmp_path / ".env")
    assert [r for r in caplog.records if r.name == "dotenv.main"]


def test_malformed_dotenv_line_leaves_only_beats_lines_on_stderr(tmp_path, capsys, caplog, dotenv_logger):
    (tmp_path / ".env").write_text(MALFORMED_ENV, encoding="utf-8")
    code = main(["beats", "s.md", "--model", "m", "--out", "b.json"], beats_factory=lambda key: None)
    assert code == 1
    assert dotenv_logger.disabled is True
    assert [r for r in caplog.records if r.name == "dotenv.main"] == []
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 1  # nothing from dotenv besides the one beats line
    assert lines[0].startswith("scenevoice beats: FAIL Missing: OPENROUTER_API_KEY")
