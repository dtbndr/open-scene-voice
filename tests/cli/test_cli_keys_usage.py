"""keys usage errors, help text and process-level behaviour."""

import subprocess
import sys

import pytest

from scenevoice.cli.main import main

NAME = "OPENROUTER_API_KEY"
SECRET = "sk-CANARY-argv-77"
USAGE = (
    "scenevoice keys: usage: scenevoice keys status | set NAME | remove NAME "
    "(NAME is one of: GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, VERTEX_AUTHORIZATION_KEY, "
    "ELEVENLABS_API_KEY, OPENROUTER_API_KEY; the value for set is read from standard input)\n"
)


@pytest.mark.parametrize(
    "argv",
    [
        ["keys", "set", NAME, SECRET],
        ["keys", "set", SECRET],
        ["keys", "status", SECRET],
        ["keys", SECRET],
        ["-x", "keys", "set", NAME, SECRET],
        ["keys", "status", "--help=" + SECRET],
        ["keys", "set", "HOME"],
        ["keys", "remove", "HOME"],
    ],
)
def test_keys_usage_errors_are_fixed_and_never_echo(key_path, feed, capsys, argv):
    feed(b"x")
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert err == USAGE
    assert SECRET not in out + err
    assert not key_path.exists()


def test_other_commands_keep_default_argparse_errors(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["plan", "a", "b"])
    assert exc.value.code == 2
    assert "unrecognized arguments: b" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(["bogus"])
    assert "invalid choice: 'bogus'" in capsys.readouterr().err


def _help(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 0
    return " ".join(capsys.readouterr().out.split())


@pytest.mark.parametrize(
    "argv",
    [["keys", "--help"], ["keys", "set", "--help"]],
)
def test_help_renders_without_stray_percent(capsys, argv):
    assert "%%" not in _help(argv, capsys)


def test_help_describes_the_key_file_and_stdin(capsys):
    assert "key file" in _help(["--help"], capsys)
    group = _help(["keys", "--help"], capsys)
    assert "Manages the per-user key file." in group
    assert "Values are read from standard input, never from the command line." in group
    assert "printf %s VALUE | scenevoice keys set NAME" in _help(["keys", "set", "--help"], capsys)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell")
def test_real_cli_with_stdin_closed(key_path):
    script = sys.executable.rsplit("/", 1)[0] + "/scenevoice"
    result = subprocess.run(f"{script} keys set {NAME} <&-", shell=True, capture_output=True, timeout=30)
    assert result.returncode == 1
    assert result.stdout == b""
    assert result.stderr == (
        f"scenevoice keys: FAIL {NAME}: pipe the value in, for example "
        f"printf %s VALUE | scenevoice keys set {NAME}\n"
    ).encode()
    assert not key_path.exists()


def test_cli_keys_does_not_import_synth():
    code = "import sys, scenevoice.cli.keys; assert 'scenevoice.synth' not in sys.modules"
    result = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
