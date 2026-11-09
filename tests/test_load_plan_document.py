import dataclasses

import pytest

from scenevoice.plan import serialize_plan
from scenevoice.synth.load_plan import load_plan
from scenevoice.synth.plan_scene import PlanScene
from scenevoice.validation import Violation
from scenevoice.validation.scene import Scene

GOOD = b'{"scenes":[{"ordinal":1,"title":"t","body":"b"}]}'


def test_plan_scene_is_frozen_with_three_fields():
    scene = PlanScene(ordinal=1, title="t", body="b")
    assert [f.name for f in dataclasses.fields(PlanScene)] == [
        "ordinal",
        "title",
        "body",
    ]
    with pytest.raises(dataclasses.FrozenInstanceError):
        scene.body = "x"  # type: ignore[misc]


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
        b"\xc3\x28",
        b"\xef\xbb\xbf" + GOOD,
        b"",
        b"   \n\t ",
        b"{not json",
        b"{",
        GOOD + b"{}",
        GOOD + b"x",
        GOOD + b"\n\x0c",  # form feed is not JSON whitespace
        GOOD + b"\n" + GOOD,
        b'{"scenes":[],"scenes":[]}',
        b'{"scenes":[{"ordinal":1,"title":"a","title":"b","body":"c"}]}',
        b'{"scenes":[{"ordinal":NaN,"title":"t","body":"b"}]}',
        b'{"scenes":[{"ordinal":1,"title":"t","body":Infinity}]}',
        b'{"scenes":[{"ordinal":-Infinity,"title":"t","body":"b"}]}',
        b"NaN",
    ],
)
def test_document_rejections_return_violation(data):
    assert isinstance(load_plan(data), Violation)


def test_deep_nesting_does_not_raise():
    assert isinstance(load_plan(b"[" * 100000), Violation)


def test_huge_integer_token_does_not_raise():
    data = b'{"scenes":[{"ordinal":' + b"1" * 5000 + b',"title":"t","body":"b"}]}'
    assert isinstance(load_plan(data), Violation)
