"""`run_plan` progress modes: json mode writes event lines on stderr, text mode is unchanged."""

import io
import json
import sys

from scenevoice.cli.plan import run_plan
from scenevoice.validation import Violation, load_scenes

BAD = b"## A\r\ntext\r\n"
GOOD = b"## A\nhello\n"


def _run(path, mode, monkeypatch):
    out, err = io.BytesIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(out, write_through=True))
    monkeypatch.setattr(sys, "stderr", err)
    code = run_plan(str(path), progress_mode=mode)
    return code, out.getvalue(), err.getvalue()


def test_json_violation_is_one_invalid_input_fail_with_line(clean_env, monkeypatch):
    script = clean_env / "s.md"
    script.write_bytes(BAD)
    violation = load_scenes(BAD)
    assert isinstance(violation, Violation)
    _, _, text_err = _run(script, "text", monkeypatch)
    code, out, err = _run(script, "json", monkeypatch)
    assert code == 1 and out == b""
    lines = err.splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["command"] == "plan" and event["event"] == "fail"
    assert event["kind"] == "invalid_input"
    assert event["line"] == violation.line and event["line"] is not None
    assert event["status"] is None and event["scene"] is None
    assert text_err == f"scenevoice plan: FAIL {event['message']}\n"


def test_json_unreadable_path_is_invalid_input_with_null_line(clean_env, monkeypatch):
    code, out, err = _run(clean_env / "missing.md", "json", monkeypatch)
    assert code == 1 and out == b""
    event = json.loads(err)
    assert event["event"] == "fail" and event["kind"] == "invalid_input"
    assert event["line"] is None and event["status"] is None
    assert "cannot read file" in event["message"]


def test_json_success_writes_plan_on_stdout_and_one_ok_line(clean_env, monkeypatch):
    script = clean_env / "s.md"
    script.write_bytes(GOOD)
    _, text_out, _ = _run(script, "text", monkeypatch)
    code, out, err = _run(script, "json", monkeypatch)
    assert code == 0 and out == text_out and out != b""
    event = json.loads(err)
    assert err.count("\n") == 1
    assert event["command"] == "plan" and event["event"] == "ok"
    assert event["message"] == str(script)


def test_text_mode_is_default_and_unchanged(clean_env, monkeypatch):
    script = clean_env / "s.md"
    script.write_bytes(GOOD)
    code, _, err = _run(script, "text", monkeypatch)
    assert code == 0 and err == f"scenevoice plan: OK {script}\n"


def test_run_plan_without_mode_is_text(clean_env, monkeypatch):
    script = clean_env / "s.md"
    script.write_bytes(GOOD)
    out, err = io.BytesIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(out, write_through=True))
    monkeypatch.setattr(sys, "stderr", err)
    assert run_plan(str(script)) == 0
    assert err.getvalue() == f"scenevoice plan: OK {script}\n"


class _LogStream:
    def __init__(self, log, name):
        self._log, self._name = log, name

    def write(self, data):
        self._log.append((self._name, data))
        return len(data)

    def flush(self):
        pass


def test_json_plan_bytes_reach_stdout_before_the_ok_line(clean_env, monkeypatch):
    script = clean_env / "s.md"
    script.write_bytes(GOOD)
    log: list = []
    stdout = _LogStream(log, "out")
    stdout.buffer = _LogStream(log, "out")
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", _LogStream(log, "err"))
    assert run_plan(str(script), progress_mode="json") == 0
    names = [name for name, data in log if data]
    assert names[0] == "out" and names[-1] == "err" and names.count("err") == 1
