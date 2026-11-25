"""regular_file_problem refuses FIFOs, devices and directories without opening them.

The helper tests pin every file class once. The reader tests below prove each reader
calls it (a FIFO would otherwise block), in a child python so a regression times out.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from paths_helper import REPO_ROOT as ROOT

from scenevoice.validation.regular_file_problem import regular_file_problem

SHORT = ROOT / "sample" / "scripts" / "short.md"
NOT_REGULAR = "not a regular file"

PLAN_CODE = (
    "import sys; from scenevoice.synth.read_plan_input import read_plan_input; "
    "r = read_plan_input(sys.argv[1], None); print(type(r).__name__, r.message)"
)
BEATS_CODE = (
    "import sys; from scenevoice.beats.read_beats_script import read_beats_script; "
    "r = read_beats_script(sys.argv[1]); print(r if isinstance(r, str) else 'OK')"
)


def run_child(code: str, *args: str, timeout: int = 10) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-c", code, *args],
        capture_output=True,
        timeout=timeout,
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
    )


@pytest.fixture
def fifo(tmp_path):
    path = tmp_path / "pipe"
    os.mkfifo(path)
    return path


def test_regular_file_is_fine(tmp_path):
    f = tmp_path / "a.md"
    f.write_bytes(b"x")
    assert regular_file_problem(f) is None


def test_symlink_to_regular_file_is_fine(tmp_path):
    f = tmp_path / "a.md"
    f.write_bytes(b"x")
    link = tmp_path / "link"
    link.symlink_to(f)
    assert regular_file_problem(link) is None


def test_missing_and_dangling_are_left_to_caller(tmp_path):
    link = tmp_path / "dangling"
    link.symlink_to(tmp_path / "nowhere")
    assert regular_file_problem(tmp_path / "missing") is None
    assert regular_file_problem(link) is None


def test_fifo_directory_and_device_are_refused(tmp_path, fifo):
    assert regular_file_problem(fifo) == NOT_REGULAR
    assert regular_file_problem(tmp_path) == NOT_REGULAR
    if not Path("/dev/null").exists():
        pytest.skip("no /dev/null")
    assert regular_file_problem("/dev/null") == NOT_REGULAR


def test_nul_in_path_is_left_to_caller():
    assert regular_file_problem("a\0b") is None


def test_read_plan_input_refuses_fifo(fifo):
    done = run_child(PLAN_CODE, str(fifo))
    assert done.returncode == 0, done.stderr
    assert done.stdout.decode().strip() == f"Violation cannot read file ({NOT_REGULAR})"


def test_read_plan_input_stdin_pipe_still_reads():
    code = (
        "import os, sys, types; from scenevoice.synth.read_plan_input import read_plan_input\n"
        "r, w = os.pipe(); os.write(w, b'hello'); os.close(w)\n"
        "stdin = types.SimpleNamespace(buffer=os.fdopen(r, 'rb'))\n"
        "sys.stdout.write(repr(read_plan_input(None, stdin)))"
    )
    done = run_child(code)
    assert done.returncode == 0, done.stderr
    assert done.stdout == b"b'hello'"


def test_beats_script_fifo_is_refused(fifo):
    done = run_child(BEATS_CODE, str(fifo))
    assert done.returncode == 0, done.stderr
    assert done.stdout.decode().strip() == f"could not read the script {fifo} ({NOT_REGULAR})"


def test_beats_script_symlink_to_valid_script_reads(tmp_path):
    link = tmp_path / "link.md"
    link.symlink_to(SHORT)
    done = run_child(BEATS_CODE, str(link))
    assert done.returncode == 0, done.stderr
    assert done.stdout.decode().strip() == "OK"
