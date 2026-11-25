import json
import os
import signal
import subprocess
import sys
import threading
import time

import pytest
from job_runner_helper import KILL_DELAY, pid_gone, wait_until

from scenevoice.keys.key_names import KEY_NAMES
from scenevoice.web import CliResult, absolute_keys_file, child_env, run_cli
from scenevoice.web.drain_pipes import drain_pipes
from scenevoice.web.running_child import RunningChild
from scenevoice.web.stop_process_group import stop_process_group

SLEEP = "import pathlib, signal, time; signal.signal(signal.SIGINT, signal.default_int_handler); pathlib.Path({ready!r}).write_text('x'); time.sleep(60)"
IGNORE = "import pathlib, signal, time; signal.signal(signal.SIGINT, signal.SIG_IGN); pathlib.Path({ready!r}).write_text('x'); time.sleep(60)"


def spawn(code: str) -> RunningChild:
    proc = subprocess.Popen(
        [sys.executable, "-c", code], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return RunningChild(proc)


def waiter(child: RunningChild) -> threading.Thread:
    thread = threading.Thread(target=child.wait, daemon=True)
    thread.start()
    return thread


def test_an_interruptible_child_gets_sigint_and_is_not_killed(killpgs, tmp_path):
    ready = tmp_path / "ready"
    child = spawn(SLEEP.format(ready=str(ready)))
    thread = waiter(child)
    wait_until(ready.exists)  # the handler is installed (a shell may have started this run with SIGINT ignored)
    stop_process_group(child, 10.0)
    thread.join(10)
    assert child.proc.returncode != -signal.SIGKILL
    assert [sig for _, sig in killpgs if sig != signal.SIGKILL] == [signal.SIGINT]
    assert [sig for _, sig in killpgs].count(signal.SIGKILL) == 1  # only the sweep at exit, no escalation before it


def test_a_child_that_ignores_sigint_is_killed_after_the_delay(killpgs, tmp_path):
    ready = tmp_path / "ready"
    child = spawn(IGNORE.format(ready=str(ready)))
    thread = waiter(child)
    wait_until(ready.exists)  # SIG_IGN is installed before the interrupt goes out
    stop_process_group(child, KILL_DELAY)
    thread.join(10)
    assert child.proc.returncode == -signal.SIGKILL
    assert pid_gone(child.proc.pid)


def test_no_signal_is_sent_once_the_child_has_been_reaped(killpgs):
    child = spawn("pass")
    child.wait()
    sent = list(killpgs)
    assert sent  # positive control
    assert child.signal_group(signal.SIGKILL) is False
    stop_process_group(child, KILL_DELAY)
    assert killpgs == sent


MIB = 1024 * 1024


def run_child(code: str):
    return subprocess.Popen(
        [sys.executable, "-c", code], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )


def drain(code: str, on_line=None, **options):
    proc = run_child(code)
    lines: list[str] = []
    handler = on_line or lines.append
    try:
        result = drain_pipes(proc.stdout, proc.stderr, handler, **options).join(timeout=20)
        proc.wait(timeout=20)
    finally:
        proc.kill()
        proc.wait(timeout=10)
    return result, lines


def test_two_one_mib_streams_written_at_once_finish_without_a_deadlock():
    code = (
        "import sys, threading\n"
        f"t = threading.Thread(target=lambda: sys.stdout.buffer.write(b'o' * {MIB}) or sys.stdout.buffer.flush())\n"
        f"t.start(); sys.stderr.buffer.write(b'e' * 1023 + b'\\n') ; [sys.stderr.buffer.write(b'e' * 1023 + b'\\n') for _ in range(1023)]; sys.stderr.buffer.flush(); t.join()"
    )
    capture, lines = drain(code)
    assert capture.total == MIB
    assert len(lines) == 1024 and lines[0] == "e" * 1023


def test_stdout_capture_keeps_the_first_bytes_up_to_the_bound_and_counts_everything():
    capture, _ = drain("import sys; sys.stdout.buffer.write(b'a' * 100 + b'b' * 400)", stdout_limit=300)
    assert capture.data == b"a" * 100 + b"b" * 200
    assert capture.total == 500


def test_stderr_lines_reach_the_callback_with_an_over_long_line_dropped_and_later_lines_kept():
    code = "import sys; sys.stderr.buffer.write(b'one\\n' + b'x' * 20 + b'\\ntwo\\n')"
    _, lines = drain(code, line_limit=10)
    assert lines == ["one", "two"]


CANARY = "canary-secret-value-123"


def env_with_keys(keys_file="/k/keys.env"):
    return {**{name: "x" for name in KEY_NAMES}, "SCENEVOICE_KEYS_FILE": keys_file, "HOME": "/h"}


def test_run_cli_runs_argument_list_in_launch_dir_with_clean_env(stub_cli, tmp_path):
    stub = stub_cli(stdout="ok\n")
    launch = tmp_path / "launch"
    launch.mkdir()
    result = run_cli(["keys", "status; echo $HOME"], cwd=launch, env=child_env(env_with_keys()), prefix=stub.prefix)
    rec = stub.recording()
    assert result == CliResult(0, "ok\n", "", False)
    assert rec["argv"] == ["keys", "status; echo $HOME"]
    assert rec["cwd"] == str(launch.resolve())
    assert all(rec["env"][name] is None for name in KEY_NAMES)
    assert rec["env"]["SCENEVOICE_KEYS_FILE"] == "/k/keys.env"


def test_stdin_reaches_the_child_and_nothing_else(stub_cli, tmp_path):
    stub = stub_cli()
    run_cli(["keys", "set", "NAME"], cwd=tmp_path, env=env_with_keys(), stdin=CANARY.encode(), prefix=stub.prefix)
    rec = stub.recording()
    stdin_arrived = rec["stdin"] == CANARY.encode()
    not_in_argv = CANARY not in "".join(rec["argv"])
    not_in_env = CANARY not in rec["env_values"]
    assert stdin_arrived
    assert not_in_argv
    assert not_in_env


def test_no_stdin_is_devnull_at_the_call(monkeypatch, tmp_path):
    seen = []

    def fake_run(*args, **kwargs):
        seen.append(kwargs)
        return subprocess.CompletedProcess(args, 0, b"", b"")

    monkeypatch.setattr(sys.modules["scenevoice.web.run_cli"].subprocess, "run", fake_run)
    run_cli(["x"], cwd=tmp_path, env={}, prefix=["p"])
    assert len(seen) == 1
    assert seen[0]["stdin"] is subprocess.DEVNULL
    assert seen[0]["input"] is None
    assert not seen[0].get("shell")


def test_utf8_output_decodes_strictly(stub_cli, tmp_path):
    text = "café \u2028 日本"
    stub = stub_cli(stdout=text, stderr_lines=[text, "b"])
    result = run_cli([], cwd=tmp_path, env={}, prefix=stub.prefix)
    assert (result.stdout, result.stderr) == (text, text + "\nb\n")


def test_nonzero_exit_is_data(stub_cli, tmp_path):
    result = run_cli([], cwd=tmp_path, env={}, prefix=stub_cli(exit_code=2, stderr_lines=["bad"]).prefix)
    assert result == CliResult(2, "", "bad\n", False)


@pytest.mark.parametrize("stream", ["stdout_hex", "stderr_hex"])
def test_undecodable_output_is_a_failed_result(stub_cli, tmp_path, stream):
    result = run_cli([], cwd=tmp_path, env={}, prefix=stub_cli(**{stream: "c328"}).prefix)
    assert result == CliResult(-1, "", "", False)


def test_timeout_kills_the_child_and_returns_a_timeout_result(stub_cli, tmp_path):
    stub = stub_cli(sleep=20)
    started = time.monotonic()
    result = run_cli([], cwd=tmp_path, env={}, prefix=stub.prefix, timeout=0.5)
    elapsed = time.monotonic() - started
    assert result == CliResult(-1, "", "", True)
    assert elapsed < 10
    with pytest.raises(ProcessLookupError):
        os.kill(stub.recording()["pid"], 0)


def test_key_file_override_reaches_child_absolute_against_server_cwd(stub_cli, tmp_path, monkeypatch):
    server_cwd = tmp_path / "server"
    launch = tmp_path / "launch"
    server_cwd.mkdir()
    launch.mkdir()
    monkeypatch.chdir(server_cwd)
    stub = stub_cli()
    env = child_env(absolute_keys_file({"SCENEVOICE_KEYS_FILE": "rel/keys.env"}))
    run_cli([], cwd=launch, env=env, prefix=stub.prefix)
    assert stub.recording()["env"]["SCENEVOICE_KEYS_FILE"] == str(server_cwd.resolve() / "rel" / "keys.env")


def test_real_cli_keys_status_runs_offline_through_the_default_prefix(key_file, tmp_path):
    path = key_file("OPENROUTER_API_KEY=abc\n")
    result = run_cli(["keys", "status"], cwd=tmp_path, env=child_env(dict(os.environ)))
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert set(payload) == {"path", "keys"}
    assert payload["path"] == str(path)
