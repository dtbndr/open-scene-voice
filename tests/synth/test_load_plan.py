import io
import json

import pytest

from scenevoice.plan import serialize_plan
from scenevoice.synth import decode_json_document
from scenevoice.synth.load_plan import load_plan
from scenevoice.synth.plan_scene import PlanScene
from scenevoice.synth.read_plan_input import read_plan_input
from scenevoice.validation import Violation
from scenevoice.validation.scene import Scene

GOOD = b'{"scenes":[{"ordinal":1,"title":"t","body":"b"}]}'


def test_round_trip_of_serialize_plan():
    scenes = [
        Scene(ordinal=1, title="One", body="alpha", line=1),
        Scene(ordinal=2, title="Zwei ü", body="beta\ngamma", line=5),
    ]
    result = load_plan(serialize_plan(scenes).encode("utf-8"))
    assert result == [
        PlanScene(1, "One", "alpha"),
        PlanScene(2, "Zwei ü", "beta\ngamma"),
    ]


def test_surrounding_json_whitespace_is_accepted():
    assert isinstance(load_plan(b" \t\r\n" + GOOD + b" \n\r\t"), list)


@pytest.mark.parametrize(
    "data",
    [
        b"\xff\xfe\x00",
        b"{not json",
        b'{"scenes":[{"ordinal":NaN,"title":"t","body":"b"}]}',
    ],
)
def test_document_rejections_return_violation(data):
    assert isinstance(load_plan(data), Violation)


def test_deep_nesting_does_not_raise():
    assert isinstance(load_plan(b"[" * 100000), Violation)


def plan(*scenes):
    return json.dumps({"scenes": list(scenes)}).encode("utf-8")


def scene(ordinal=1, title="t", body="b"):
    return {"ordinal": ordinal, "title": title, "body": body}


def raw(ordinal_token="1", title='"t"', body='"b"'):
    return (
        f'{{"scenes":[{{"ordinal":{ordinal_token},"title":{title},"body":{body}}}]}}'
    ).encode()


# P1 (core flow): a plan the synth step cannot read stops before any paid call.
# One row per equivalence class; hand-written variants collapse into them.
@pytest.mark.parametrize(
    "data",
    [
        b"[]",
        b'{"scenes":[{"ordinal":1,"title":"t","body":"b"}],"extra":1}',
        b'{"scenes":[]}',
        b'{"scenes":[1]}',
        b'{"scenes":[{"ordinal":1,"body":"b"}]}',
        b'{"scenes":[{"ordinal":1,"title":"t","body":"b","x":1}]}',
    ],
)
def test_shape_rejections_are_violations(data):
    assert isinstance(load_plan(data), Violation)


@pytest.mark.parametrize("token", ["true", "1.0", '"1"'])
def test_ordinal_token_rejected(token):
    assert isinstance(load_plan(raw(ordinal_token=token)), Violation)


def test_ordinal_consecutive_from_one_accepted():
    result = load_plan(plan(scene(1), scene(2, "u", "c"), scene(3)))
    assert result == [
        PlanScene(1, "t", "b"),
        PlanScene(2, "u", "c"),
        PlanScene(3, "t", "b"),
    ]
    assert all(type(s.ordinal) is int for s in result)


@pytest.mark.parametrize("ordinals", [[0], [1, 3], [1, 1], [2, 1]])
def test_ordinal_sequence_rejected(ordinals):
    assert isinstance(load_plan(plan(*[scene(o) for o in ordinals])), Violation)


def test_later_scene_bool_ordinal_rejected():
    assert isinstance(load_plan(plan(scene(1), scene(True))), Violation)


@pytest.mark.parametrize("title", ["", "日本語 ü"])
def test_title_any_string_accepted(title):
    result = load_plan(plan(scene(title=title)))
    assert result == [PlanScene(1, title, "b")]


@pytest.mark.parametrize(("field", "token"), [("title", "1"), ("body", "null")])
def test_title_and_body_non_string_rejected(field, token):
    assert isinstance(load_plan(raw(**{field: token})), Violation)


@pytest.mark.parametrize("body", ["", "\n", "　"])
def test_body_blank_rejected(body):
    assert isinstance(load_plan(plan(scene(body=body))), Violation)


def test_body_non_blank_accepted():
    assert load_plan(plan(scene(body=" a "))) == [PlanScene(1, "t", " a ")]


@pytest.mark.parametrize("body", ['"\\ud800"'], ids=["lone"])
def test_body_with_surrogate_is_violation_not_exception(body):
    assert isinstance(load_plan(raw(body=body)), Violation)


def test_title_with_lone_surrogate_accepted():
    result = load_plan(raw(title='"\\ud800"'))
    assert result == [PlanScene(1, "\ud800", "b")]


def test_paired_surrogate_escape_in_body_accepted():
    assert load_plan(raw(body='"\\ud83d\\ude00"')) == [PlanScene(1, "t", "\U0001f600")]


@pytest.mark.parametrize(
    "data",
    [
        b'{"a": "\xff"}',
        b'{"a": 1} x',
        b'{"a": 1, "a": 2}',
        b'{"a": NaN}',
        b"[" * 100000 + b"]" * 100000,
        b"",
    ],
    ids=["bad-utf8", "trailing", "duplicate", "nan", "deep", "empty"],
)
def test_rejects_with_violation(data: bytes) -> None:
    assert isinstance(decode_json_document(data), Violation)


def test_accepts_document_with_trailing_whitespace() -> None:
    assert decode_json_document(b' {"a": [1, 2.5, null]}\n') == {"a": [1, 2.5, None]}


def test_accepts_non_object_document() -> None:
    assert decode_json_document(b"[1]") == [1]


class FakeStdin:
    def __init__(self, data: bytes):
        self.buffer = io.BytesIO(data)


class BrokenBuffer:
    def read(self):
        raise OSError(5, "Input/output error")


class BrokenStdin:
    buffer = BrokenBuffer()


class NoBufferStdin:
    pass


def _is_read_failure(result):
    return isinstance(result, Violation) and "cannot read file (" in result.message


def test_readable_file_returns_bytes(tmp_path):
    path = tmp_path / "plan.json"
    path.write_bytes(b"[1]")
    assert read_plan_input(str(path), None) == b"[1]"


def test_path_wins_over_stdin_which_is_not_touched(tmp_path):
    path = tmp_path / "plan.json"
    path.write_bytes(b"from file")
    assert read_plan_input(path, NoBufferStdin()) == b"from file"


def test_missing_path_is_a_read_failure(tmp_path):
    assert _is_read_failure(read_plan_input(str(tmp_path / "nope.json"), None))


def test_empty_stdin_is_a_read_failure():
    assert _is_read_failure(read_plan_input(None, FakeStdin(b"")))


def test_non_empty_stdin_returns_bytes():
    assert read_plan_input(None, FakeStdin(b"{}")) == b"{}"
