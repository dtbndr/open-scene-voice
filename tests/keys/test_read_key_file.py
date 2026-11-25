import logging
import os
import subprocess
import sys

import pytest
from keys_helper import CANARY, posix_only
from paths_helper import REPO_ROOT

from scenevoice.keys.read_key_file import read_key_file
from scenevoice.validation import Violation

FIVE = """\
# a comment
GOOGLE_CLOUD_PROJECT=my-project

GOOGLE_CLOUD_LOCATION="us-central1"
VERTEX_AUTHORIZATION_KEY='vk-1'
ELEVENLABS_API_KEY=el-1
OPENROUTER_API_KEY=
"""


def write(tmp_path, text, mode=0o600):
    f = tmp_path / "keys.env"
    f.write_text(text)
    f.chmod(mode)
    return f


def run_child(code, *args, timeout=10):
    return subprocess.run(
        [sys.executable, "-c", code, *args], capture_output=True, timeout=timeout, cwd=REPO_ROOT, stdin=subprocess.DEVNULL
    )


CHILD = (
    "import sys; from scenevoice.keys.read_key_file import read_key_file; "
    "r = read_key_file(sys.argv[1], None); print(r.rule, r.message, r.line)"
)


def test_missing_file_is_empty_result(tmp_path):
    assert read_key_file(tmp_path / "nope", None) == {}


def test_five_names_parsed_with_comments_blanks_and_quotes(tmp_path):
    assert read_key_file(write(tmp_path, FIVE), None) == {
        "GOOGLE_CLOUD_PROJECT": "my-project",
        "GOOGLE_CLOUD_LOCATION": "us-central1",
        "VERTEX_AUTHORIZATION_KEY": "vk-1",
        "ELEVENLABS_API_KEY": "el-1",
        "OPENROUTER_API_KEY": "",
    }


def test_unknown_names_are_ignored(tmp_path):
    f = write(tmp_path, f"OTHER={CANARY}\nELEVENLABS_API_KEY=el-1\n")
    assert read_key_file(f, None) == {"ELEVENLABS_API_KEY": "el-1"}


def test_no_interpolation(tmp_path):
    f = write(tmp_path, "ELEVENLABS_API_KEY=${HOME}x\n")
    assert read_key_file(f, None) == {"ELEVENLABS_API_KEY": "${HOME}x"}


def test_malformed_line_names_path_and_line_not_content(tmp_path):
    f = write(tmp_path, f"ELEVENLABS_API_KEY=el-1\n{CANARY} oops without equals\n")
    result = read_key_file(f, None)
    assert result == Violation("key-file", f"key file {f}: line 2 is not NAME=value")
    assert result.line is None
    assert CANARY not in result.message


def test_directory_is_not_a_regular_file(tmp_path):
    assert read_key_file(tmp_path, None) == Violation("key-file", f"key file {tmp_path} is not a regular file")


@posix_only
def test_fifo_is_refused_without_hanging(tmp_path):
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    out = run_child(CHILD, str(fifo)).stdout.decode()
    assert out.strip() == f"key-file key file {fifo} is not a regular file None"


def test_invalid_utf8_is_could_not_read(tmp_path):
    f = tmp_path / "keys.env"
    f.write_bytes(b"ELEVENLABS_API_KEY=\xff\xfe" + CANARY.encode() + b"\n")
    result = read_key_file(f, None)
    assert result == Violation("key-file", f"could not read key file {f}")
    assert CANARY not in result.message


@posix_only
def test_unreadable_file_is_could_not_read(tmp_path):
    f = write(tmp_path, "A=b\n", mode=0o000)
    if os.access(f, os.R_OK):
        pytest.skip("running as a user that ignores modes")
    assert read_key_file(f, None) == Violation("key-file", f"could not read key file {f}")


@posix_only
def test_loose_mode_warns_once_and_still_reads(tmp_path):
    f = write(tmp_path, "ELEVENLABS_API_KEY=el-1\n", mode=0o644)
    warnings: list[str] = []
    result = read_key_file(f, warnings.append)
    assert result == {"ELEVENLABS_API_KEY": "el-1"}
    assert warnings == [f"key file {f} can be read by other users; run chmod 600 {f}"]


@posix_only
def test_owner_only_mode_does_not_warn(tmp_path):
    warnings: list[str] = []
    read_key_file(write(tmp_path, "ELEVENLABS_API_KEY=el-1\n"), warnings.append)
    assert warnings == []


@posix_only
def test_canary_never_in_messages_or_logs(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    warnings: list[str] = []
    loose = write(tmp_path, f"ELEVENLABS_API_KEY={CANARY}\n", mode=0o644)
    read_key_file(loose, warnings.append)
    bad = tmp_path / "bad.env"
    bad.write_text(f"ELEVENLABS_API_KEY={CANARY}\nnot a binding {CANARY}\n")
    bad.chmod(0o644)
    result = read_key_file(bad, warnings.append)
    assert isinstance(result, Violation)
    assert CANARY not in result.message
    assert all(CANARY not in w for w in warnings)
    assert all(CANARY not in r.getMessage() for r in caplog.records)


@posix_only
def test_malformed_loose_file_returns_violation_and_warns_once(tmp_path):
    f = write(tmp_path, "ELEVENLABS_API_KEY=el-1\nnot a binding\n", mode=0o644)
    warnings: list[str] = []
    result = read_key_file(f, warnings.append)
    assert result == Violation("key-file", f"key file {f}: line 2 is not NAME=value")
    assert warnings == [f"key file {f} can be read by other users; run chmod 600 {f}"]

