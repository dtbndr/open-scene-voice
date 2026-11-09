import json
import os
from pathlib import Path

import pytest

from scenevoice.cli.main import main
from scenevoice.validation import Violation, load_scenes

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("name", ["sample/scripts/short.md", "sample/scripts/long.md"])
def test_plan_success_writes_plan_to_stdout_and_ok_to_stderr(name, capsysbinary):
    path = str(ROOT / name)
    scenes = load_scenes((ROOT / name).read_bytes())
    assert main(["plan", path]) == 0
    captured = capsysbinary.readouterr()
    assert captured.err == f"scenevoice plan: OK {path}\n".encode()
    assert captured.out.endswith(b"\n")
    plan = json.loads(captured.out.decode("utf-8"))
    assert len(plan["scenes"]) == len(scenes)
    assert plan["scenes"][0]["ordinal"] == 1
    assert plan["scenes"][0]["title"] == scenes[0].title
    assert plan["scenes"][0]["body"] == scenes[0].body


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
    assert captured.err.startswith(
        f"scenevoice plan: FAIL {path}: cannot read file (".encode()
    )
    assert reason.encode("utf-8") in captured.err
    assert b"Traceback" not in captured.err
    assert captured.out == b""
    assert called == []


def test_plan_missing_file_renders_cannot_read(tmp_path, capsysbinary, monkeypatch):
    _assert_cannot_read(
        tmp_path / "missing.md", "No such file or directory", capsysbinary, monkeypatch
    )


def test_plan_directory_renders_cannot_read(tmp_path, capsysbinary, monkeypatch):
    _assert_cannot_read(tmp_path, "Is a directory", capsysbinary, monkeypatch)


@pytest.mark.skipif(os.geteuid() == 0, reason="chmod 000 does not block root reads")
def test_plan_unreadable_file_renders_cannot_read(tmp_path, capsysbinary, monkeypatch):
    script = tmp_path / "locked.md"
    script.write_bytes(b"data")
    script.chmod(0o000)
    try:
        _assert_cannot_read(script, "Permission denied", capsysbinary, monkeypatch)
    finally:
        script.chmod(0o600)
