"""Pin the one-line JSON event contract written to stderr by --progress json.

Stderr contract: each JSON line is one event; any non-JSON line on stderr is
raw text (for example an argparse error) and consumers must tolerate it.
"""

import json

import pytest

from scenevoice.progress import KINDS, PROGRESS_MODES, event_line


def test_kinds_and_modes_are_fixed() -> None:
    assert KINDS == (
        "missing_key",
        "bad_key",
        "quota",
        "provider_down",
        "invalid_input",
        "other",
    )
    assert PROGRESS_MODES == ("text", "json")


def test_note_exact_bytes() -> None:
    assert event_line("plan", "note", "hello") == (
        '{"command":"plan","event":"note","message":"hello"}\n'
    )


def test_ok_exact_bytes() -> None:
    assert event_line("pack", "ok", "done") == (
        '{"command":"pack","event":"ok","message":"done"}\n'
    )


def test_scene_started_exact_bytes() -> None:
    line = event_line("synth", "scene", "Scene 3", state="started", scene=3, total=5)
    assert line == (
        '{"command":"synth","event":"scene","message":"Scene 3",'
        '"state":"started","scene":3,"total":5}\n'
    )


def test_scene_done_with_path_exact_bytes() -> None:
    line = event_line(
        "synth", "scene", "Scene 3", path="audio/003.wav", total=5, scene=3, state="done"
    )
    assert line == (
        '{"command":"synth","event":"scene","message":"Scene 3",'
        '"state":"done","scene":3,"total":5,"path":"audio/003.wav"}\n'
    )


def test_fail_exact_bytes_all_fields() -> None:
    line = event_line("synth", "fail", "no", status=429, line=7, scene=2, kind="quota")
    assert line == (
        '{"command":"synth","event":"fail","message":"no",'
        '"kind":"quota","scene":2,"line":7,"status":429}\n'
    )


def test_fail_optional_fields_are_null() -> None:
    line = event_line("align", "fail", "x", kind="other")
    assert line == (
        '{"command":"align","event":"fail","message":"x",'
        '"kind":"other","scene":null,"line":null,"status":null}\n'
    )


def test_single_physical_line() -> None:
    line = event_line("plan", "note", "a\nb\r\nc")
    assert line.endswith("\n")
    assert line.count("\n") == 1
    assert json.loads(line)["message"] == "a\nb\r\nc"


def test_output_is_ascii_with_escapes() -> None:
    line = event_line("plan", "note", "café ☃ \ud800")
    assert line.isascii()
    assert "\\u00e9" in line
    assert "\\u2603" in line
    assert "\\ud800" in line


@pytest.mark.parametrize("kind", [None, "nope"])
def test_fail_rejects_missing_or_unknown_kind(kind: object) -> None:
    fields = {} if kind is None else {"kind": kind}
    with pytest.raises(ValueError):
        event_line("synth", "fail", "x", **fields)


@pytest.mark.parametrize("command", ["run"])
def test_rejects_unknown_command(command: str) -> None:
    with pytest.raises(ValueError):
        event_line(command, "note", "x")


@pytest.mark.parametrize("event", ["start"])
def test_rejects_unknown_event(event: str) -> None:
    with pytest.raises(ValueError):
        event_line("plan", event, "x")


@pytest.mark.parametrize(
    ("event", "fields"),
    [
        ("note", {"state": "started"}),
        ("scene", {"state": "started", "scene": 1, "total": 2, "kind": "quota"}),
        ("fail", {"kind": "quota", "path": "a"}),
    ],
)
def test_rejects_unknown_field_for_event(event: str, fields: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        event_line("synth", event, "x", **fields)


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"state": "paused", "scene": 1, "total": 2},
    ],
)
def test_scene_requires_state_scene_total(fields: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        event_line("synth", "scene", "x", **fields)
