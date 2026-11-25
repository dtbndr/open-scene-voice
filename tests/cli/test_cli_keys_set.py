import os
import stat
import sys

import pytest
from common_helper import run
from keys_helper import CANARY, posix_only, seed

from scenevoice.cli.main import main
from scenevoice.keys import read_key_file

NAME = "OPENROUTER_API_KEY"
PIPE_HINT = (
    f"scenevoice keys: FAIL {NAME}: pipe the value in, for example "
    f"printf %s VALUE | scenevoice keys set {NAME}\n"
)


def _set(feed, data, name=NAME):
    feed(data)
    return main(["keys", "set", name])


@pytest.mark.parametrize("closed", [False, True], ids=["terminal", "closed"])
def test_terminal_or_closed_stdin_refused_before_reading(key_path, feed, monkeypatch, capsys, closed):
    fake = feed(CANARY.encode(), tty=True)
    if closed:
        monkeypatch.setattr(sys, "stdin", None)
    assert main(["keys", "set", NAME]) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err == PIPE_HINT
    assert fake.buffer.reads == 0
    assert not key_path.exists()


def test_set_saves_and_confirms(key_path, feed, capsys):
    assert _set(feed, CANARY.encode() + b"\n") == 0
    out, err = capsys.readouterr()
    assert out == ""
    assert err == f"scenevoice keys: saved {NAME}\n"
    assert key_path.read_text() == f"{NAME}='{CANARY}'\n"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"abc\n", "abc"),
        (b"abc", "abc"),
        (b"  abc\t\n", "  abc\t"),
    ],
)
def test_strip_exactly_one_trailing_newline(key_path, feed, data, expected):
    assert _set(feed, data) == 0
    assert read_key_file(key_path, None) == {NAME: expected}


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "the value is empty"),
        (b"   \n", "the value is blank"),
        (b"a\nb", "the value must not contain a line break"),
        (b"a\x00b", "the value must not contain a NUL character"),
        (b"\xff\xfe" + CANARY.encode(), "the value is not valid UTF-8"),
    ],
)
def test_bad_value_fails_and_leaves_file(key_path, feed, capsys, data, message):
    before = seed(key_path, "ELEVENLABS_API_KEY='el'\n")
    assert _set(feed, data) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err == f"scenevoice keys: FAIL {NAME}: {message}\n"
    assert key_path.read_bytes() == before


def test_set_on_malformed_file_fails_and_keeps_it(key_path, feed, capsys):
    before = seed(key_path, f"OPENROUTER_API_KEY='x'\n{CANARY} oops without equals\n")
    assert _set(feed, b"new\n") == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err == f"scenevoice keys: FAIL key file {key_path}: line 2 is not NAME=value\n"
    assert key_path.read_bytes() == before


@posix_only
def test_file_is_0600_after_set(key_path, feed):
    assert _set(feed, b"abc") == 0
    assert stat.S_IMODE(os.stat(key_path).st_mode) == 0o600


@posix_only
def test_loose_mode_note_once_for_set(key_path, feed, capsys):
    seed(key_path, "ELEVENLABS_API_KEY='el'\n", mode=0o644)
    assert _set(feed, b"abc") == 0
    out, err = capsys.readouterr()
    assert out == ""
    assert err == (
        f"scenevoice keys: NOTE key file {key_path} can be read by other users; run chmod 600 {key_path}\n"
        f"scenevoice keys: saved {NAME}\n"
    )


def test_real_cli_set_pipes_stdin(key_path):
    result = run(["keys", "set", NAME], input=CANARY.encode() + b"\n")
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr == f"scenevoice keys: saved {NAME}\n".encode()
    assert key_path.read_text() == f"{NAME}='{CANARY}'\n"


def test_real_cli_set_empty_stdin_fails(key_path):
    result = run(["keys", "set", NAME], input=b"")
    assert result.returncode == 1
    assert result.stderr == f"scenevoice keys: FAIL {NAME}: the value is empty\n".encode()
    assert not key_path.exists()
