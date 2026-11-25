import subprocess
import sys

import pytest

from scenevoice.web import run_opener


@pytest.fixture
def calls(monkeypatch):
    seen = []

    def fake_run(*args, **kwargs):
        seen.append((args, kwargs))
        return subprocess.CompletedProcess(args[0], 0)

    # the fake replaces subprocess.run: no test here ever starts `open` or `xdg-open`
    monkeypatch.setattr(sys.modules["scenevoice.web.run_opener"].subprocess, "run", fake_run)
    return seen


def test_the_argument_list_runs_without_a_shell_with_no_stdin_and_a_ten_second_timeout(calls):
    assert run_opener(["open", "/ws/my video; rm -rf /"]) == 0
    assert len(calls) == 1  # positive control: the fake was the one called
    args, kwargs = calls[0]
    assert args == (["open", "/ws/my video; rm -rf /"],)
    assert kwargs["shell"] is False
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["timeout"] == 10
    assert kwargs["check"] is False
    assert kwargs["stdout"] is subprocess.DEVNULL and kwargs["stderr"] is subprocess.DEVNULL


def test_the_exit_code_is_returned(monkeypatch, calls):
    monkeypatch.setattr(
        sys.modules["scenevoice.web.run_opener"].subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 3),
    )
    assert run_opener(["open", "/d"]) == 3


@pytest.mark.parametrize("failure", [subprocess.TimeoutExpired("open", 10), FileNotFoundError("open"), PermissionError("x")])
def test_a_timeout_or_an_oserror_is_a_non_zero_result_and_never_raised(monkeypatch, failure):
    attempts = []

    def fake_run(*args, **kwargs):
        attempts.append(args)
        raise failure

    monkeypatch.setattr(sys.modules["scenevoice.web.run_opener"].subprocess, "run", fake_run)
    assert run_opener(["xdg-open", "/d"]) == -1
    assert len(attempts) == 1
