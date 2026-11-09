import io
import json

import pytest
from wav_helper import wav_audio

from scenevoice.cli.main import main

ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": "dummy-key-value",
}
AUDIO = wav_audio()


class Stdin:
    def __init__(self, text):
        self.buffer = io.BytesIO(text.encode("utf-8"))

    def isatty(self):
        return False


class Fake:
    def __init__(self):
        self.envs = []
        self.calls = []

    def factory(self, env, model):
        self.envs.append(env)

        def provider(request):
            body = request.body
            voice = request.voice
            language = request.language
            style = request.instruction
            self.calls.append((body, voice, language, style))
            return AUDIO

        return provider


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name, value in ENV.items():
        monkeypatch.setenv(name, value)
    plan = json.dumps({"scenes": [{"ordinal": 1, "title": "t", "body": "body one"}]})
    monkeypatch.setattr("sys.stdin", Stdin(plan))
    return tmp_path


def run(isolated, capsys, *extra):
    fake = Fake()
    code = main(
        ["synth", "--out", str(isolated / "out"), "--voice", "Charon", "--model", "gemini-3.8-flash-tts", *extra],
        provider_factory=fake.factory,
    )
    assert capsys.readouterr().out == ""
    return code, fake


def test_language_defaults_to_en_gb(isolated, capsys):
    code, fake = run(isolated, capsys)
    assert code == 0
    assert [c[2] for c in fake.calls] == ["en-GB"]
    assert [c[1] for c in fake.calls] == ["Charon"]


def test_without_instruction_provider_receives_style_none(isolated, capsys):
    code, fake = run(isolated, capsys)
    assert code == 0
    assert fake.calls == [("body one", "Charon", "en-GB", None)]


def test_explicit_values_override_defaults(isolated, capsys):
    code, fake = run(isolated, capsys, "--language", "fr-FR", "--instruction=Say it.")
    assert code == 0
    assert fake.calls[0] == ("body one", "Charon", "fr-FR", "Say it.")


def test_unencodable_instruction_is_exit_1_not_usage(isolated, capsys):
    code, fake = run(isolated, capsys, "--instruction=\ud800")
    assert code == 1
    assert fake.calls == []


# --- D2: real-environment wiring ---


def test_env_comes_from_process_environ_and_cwd_dotenv(isolated, capsys, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION")
    (isolated / ".env").write_text("GOOGLE_CLOUD_LOCATION=from-dotenv\n")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "from-process")
    code, fake = run(isolated, capsys)
    assert code == 0
    assert fake.envs[0]["GOOGLE_CLOUD_PROJECT"] == "from-process"
    assert fake.envs[0]["GOOGLE_CLOUD_LOCATION"] == "from-dotenv"


def test_dotenv_is_read_relative_to_cwd_not_elsewhere(isolated, capsys, monkeypatch):
    # Positive control: a .env elsewhere than the cwd must not be used.
    other = isolated / "other"
    other.mkdir()
    (other / ".env").write_text("GOOGLE_CLOUD_LOCATION=elsewhere\n")
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION")
    code, fake = run(isolated, capsys)
    assert code == 1
    assert fake.envs == []


def test_stdin_and_stderr_are_the_live_streams(isolated, capsys, monkeypatch):
    err = io.StringIO()
    monkeypatch.setattr("sys.stderr", err)
    code, fake = run(isolated, capsys)
    assert code == 0
    assert len(fake.calls) == 1  # plan came from the patched sys.stdin
    assert "scenevoice synth: OK" in err.getvalue()


def test_exit_one_on_operational_failure_with_empty_stdout(isolated, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", Stdin("not json"))
    code, fake = run(isolated, capsys)
    assert code == 1
    assert fake.calls == []


# --- D2: python-dotenv silence ---


@pytest.fixture
def dotenv_logger():
    import logging

    logger = logging.getLogger("dotenv.main")
    saved = (logger.disabled, logger.level)
    logger.disabled = False
    logger.setLevel(logging.NOTSET)
    yield logger
    logger.disabled, level = saved
    logger.setLevel(level)


def test_dotenv_logger_is_silenced_after_the_command(isolated, capsys, dotenv_logger):
    import logging

    assert dotenv_logger.isEnabledFor(logging.WARNING)  # positive control
    code, _ = run(isolated, capsys)
    assert code == 0
    assert dotenv_logger.disabled or not dotenv_logger.isEnabledFor(logging.WARNING)


def test_secondary_malformed_dotenv_line_yields_only_prefixed_stderr(
    isolated, capsys, dotenv_logger
):
    (isolated / ".env").write_text("this line is not valid\nOTHER=1\n")
    code = main(
        ["synth", "--out", str(isolated / "out"), "--voice", "Charon", "--model", "gemini-3.8-flash-tts"],
        provider_factory=Fake().factory,
    )
    captured = capsys.readouterr()
    lines = captured.err.splitlines()
    assert code == 0
    assert captured.out == ""
    assert lines and all(line.startswith("scenevoice synth:") for line in lines)


# --- D2: second backstop (run_synth redaction), not the proof ---


def test_provider_error_containing_key_never_reaches_stderr(isolated, capsys):
    from scenevoice.synth import ProviderError

    def factory(env, model):
        def provider(request):
            raise ProviderError(f"HTTP 400 body echoed {env['VERTEX_AUTHORIZATION_KEY']}")

        return provider

    code = main(
        ["synth", "--out", str(isolated / "out"), "--voice", "Charon", "--model", "gemini-3.8-flash-tts"],
        provider_factory=factory,
    )
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "dummy-key-value" not in captured.err
    assert "scenevoice synth:" in captured.err
