"""`scenevoice plan` wiring: one test per rule family, not a re-pin of each rule.

Validation messages and lines belong to the validation units; the plan bytes belong to
serialize_plan. Here: the command calls them and renders OK / FAIL on the right stream.
"""

import os

import pytest
from paths_helper import REPO_ROOT as ROOT

from scenevoice.cli.main import main
from scenevoice.plan import serialize_plan
from scenevoice.validation import Violation, load_scenes


@pytest.mark.parametrize(
    "name",
    ["sample/scripts/short.md", "sample/scripts/long.md", "non-ascii"],
)
def test_plan_success_writes_plan_to_stdout_and_ok_to_stderr(name, tmp_path, capsysbinary):
    if name == "non-ascii":
        script = tmp_path / "script.md"
        script.write_bytes("## Café 日本\nnaïve\n".encode())
        data, path = script.read_bytes(), str(script)
    else:
        data, path = (ROOT / name).read_bytes(), str(ROOT / name)
    scenes = load_scenes(data)
    assert not isinstance(scenes, Violation)
    assert main(["plan", path]) == 0
    captured = capsysbinary.readouterr()
    assert captured.err == f"scenevoice plan: OK {path}\n".encode()
    assert captured.out == serialize_plan(scenes).encode("utf-8")


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"## A\n\xff\xfe\n", id="decode_script"),
        pytest.param(b"## A\r\ntext\r\n", id="check_cr"),
        pytest.param(b"## A\ntext\x07\n", id="check_controls"),
        pytest.param(b"## A\n \t\n", id="parse_scenes"),
    ],
)
def test_plan_reports_the_validation_violation_and_writes_no_plan(data, tmp_path, capsysbinary):
    script = tmp_path / "script.md"
    script.write_bytes(data)
    violation = load_scenes(data)
    assert isinstance(violation, Violation)
    assert main(["plan", str(script)]) == 1
    captured = capsysbinary.readouterr()
    assert captured.err == f"scenevoice plan: FAIL {script}: {violation.message} (line {violation.line})\n".encode()
    assert captured.out == b""


@pytest.mark.parametrize(
    "line, suffix",
    [(7, " (line 7)"), (None, "")],
)
def test_plan_violation_renders_fail_line(line, suffix, tmp_path, monkeypatch, capsysbinary):
    script = tmp_path / "script.md"
    script.write_bytes(b"anything")
    violation = Violation(rule="test-rule", message="bad thing", line=line)
    monkeypatch.setattr("scenevoice.cli.plan.load_scenes", lambda data: violation)
    assert main(["plan", str(script)]) == 1
    captured = capsysbinary.readouterr()
    assert captured.err == f"scenevoice plan: FAIL {script}: bad thing{suffix}\n".encode()
    assert captured.out == b""


def _assert_cannot_read(path, reason, capsysbinary, monkeypatch):
    called = []
    monkeypatch.setattr(
        "scenevoice.cli.plan.load_scenes", lambda data: called.append(data)
    )
    assert main(["plan", str(path)]) == 1
    captured = capsysbinary.readouterr()
    assert captured.err == f"scenevoice plan: FAIL {path}: cannot read file ({reason})\n".encode()
    assert captured.out == b""
    assert called == []


def test_plan_missing_file_renders_cannot_read(tmp_path, capsysbinary, monkeypatch):
    _assert_cannot_read(
        tmp_path / "missing.md", "No such file or directory", capsysbinary, monkeypatch
    )


def test_plan_directory_renders_cannot_read(tmp_path, capsysbinary, monkeypatch):
    _assert_cannot_read(tmp_path, "not a regular file", capsysbinary, monkeypatch)


@pytest.mark.skipif(os.geteuid() == 0, reason="chmod 000 does not block root reads")
def test_plan_unreadable_file_renders_cannot_read(tmp_path, capsysbinary, monkeypatch):
    script = tmp_path / "locked.md"
    script.write_bytes(b"data")
    script.chmod(0o000)
    try:
        _assert_cannot_read(script, "Permission denied", capsysbinary, monkeypatch)
    finally:
        script.chmod(0o600)
