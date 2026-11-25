import hashlib
import json
import os
import stat
import threading
from pathlib import Path

import pytest

from scenevoice.progress import event_line
from scenevoice.progress.event_line import COMMANDS as CLI_COMMANDS
from scenevoice.progress.event_line import EVENTS as CLI_EVENTS
from scenevoice.progress.kinds import KINDS
from scenevoice.web import (
    COMMANDS,
    EVENT_NAMES,
    FAILURE_KINDS,
    SCENE_STATES,
    CliResult,
    PlannedScene,
    PlanProblem,
    PlanRun,
    parse_event_line,
    run_plan,
    script_revision,
)


def test_the_server_vocabularies_equal_the_childs() -> None:
    assert FAILURE_KINDS == KINDS
    assert COMMANDS == CLI_COMMANDS
    assert EVENT_NAMES == CLI_EVENTS


@pytest.mark.parametrize("state", SCENE_STATES)
def test_every_scene_state_the_server_knows_is_one_the_child_writes(state: str) -> None:
    assert event_line("synth", "scene", "m", state=state, scene=1, total=1)
    with pytest.raises(ValueError):
        event_line("synth", "scene", "m", state="paused", scene=1, total=1)


def test_every_line_the_child_can_write_parses_with_all_its_fields() -> None:
    lines = {
        "scene": event_line("synth", "scene", "m", state="done", scene=2, total=3, path="audio/002.wav"),
        "note": event_line("align", "note", "m"),
        "ok": event_line("pack", "ok", "m"),
        "fail": event_line("beats", "fail", "m", kind="quota", scene=2, line=4, status=429),
    }
    for name, text in lines.items():
        parsed = parse_event_line(text)
        assert parsed is not None
        assert parsed["type"] == name
        assert parsed["message"] == "m"
    assert parse_event_line(lines["scene"]) == {
        "type": "scene", "command": "synth", "message": "m", "state": "done", "scene": 2, "total": 3, "path": "audio/002.wav",
    }
    assert parse_event_line(lines["fail"]) == {
        "type": "fail", "command": "beats", "message": "m", "kind": "quota", "scene": 2, "line": 4, "status": 429,
    }


PLAN = json.dumps(
    {"scenes": [{"ordinal": 1, "title": "One", "body": "Hello\u2028there"}, {"ordinal": 2, "title": "Two", "body": "x"}]},
    ensure_ascii=False,
) + "\n"
FAIL = '{{"event": "fail", "kind": "invalid_input", "message": "{path}: Scene 2 is empty (line 7)", "line": 7}}'


class FakeRun:
    """Stands in for the bound CLI runner: records the call and what the temp file looked like at call time."""

    def __init__(self, result: CliResult) -> None:
        self.result = result
        self.calls: list[tuple[list[str], bytes | None, float]] = []
        self.seen: dict[str, object] = {}

    def __call__(self, args, stdin=None, timeout=30.0) -> CliResult:
        self.calls.append((list(args), stdin, timeout))
        path = Path(args[-1])
        self.seen = {"mode": stat.S_IMODE(os.stat(path).st_mode), "bytes": path.read_bytes(), "parent": path.parent}
        return self.result


@pytest.fixture
def launch(tmp_path):
    directory = tmp_path / "launch"
    directory.mkdir(mode=0o700)
    return directory


def ok(stdout=PLAN):
    return CliResult(0, stdout, "", False)


def test_a_passed_plan_returns_the_exact_stdout_bytes_the_scenes_and_the_revision_of_the_script_bytes(launch):
    run = FakeRun(ok())
    result = run_plan(b"a\r\nb", run, launch, threading.Lock())
    assert result == PlanRun(
        PLAN.encode("utf-8"),
        (PlannedScene(1, "One", "Hello\u2028there"), PlannedScene(2, "Two", "x")),
        hashlib.sha256(b"a\r\nb").hexdigest(),
    )
    assert len(run.calls) == 1  # positive control: the answer came from the run


def test_the_revision_is_the_sha256_hex_of_the_exact_bytes():
    assert script_revision(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert script_revision(b"abc ") != script_revision(b"abd ") != script_revision(b"abc")


def test_the_bytes_go_to_a_private_temp_file_in_the_launch_directory_that_is_deleted_afterwards(launch):
    run = FakeRun(ok())
    run_plan(b"script bytes", run, launch, threading.Lock(), 3.5)
    argv, stdin, timeout = run.calls[0]
    assert argv[:3] == ["plan", "--progress", "json"] and Path(argv[3]).is_absolute() and len(argv) == 4
    assert run.seen == {"mode": 0o600, "bytes": b"script bytes", "parent": launch}
    assert (stdin, timeout) == (None, 3.5)
    assert list(launch.iterdir()) == []


@pytest.mark.parametrize(
    "result",
    [
        CliResult(-1, "", "", True),
        CliResult(2, "", "usage", False),
        ok("not json"),
        ok('{"scenes": [{"ordinal": 1, "title": "t"}]}'),
    ],
)
def test_a_cli_failure_or_an_unusable_plan_is_none_and_the_temp_file_is_still_deleted(launch, result):
    assert run_plan(b"x", FakeRun(result), launch, threading.Lock()) is None
    assert list(launch.iterdir()) == []


def test_a_script_problem_is_the_one_problem_without_the_temp_path(launch):
    run = FakeRun(CliResult(1, "", "", False))

    def with_path(args, stdin=None, timeout=30.0):
        return CliResult(1, "", FAIL.format(path=args[-1]), False)

    problem = run_plan(b"x", with_path, launch, threading.Lock())
    assert problem == PlanProblem(7, "Scene 2 is empty")
    assert run.calls == []  # positive control: with_path, not FakeRun, produced it
