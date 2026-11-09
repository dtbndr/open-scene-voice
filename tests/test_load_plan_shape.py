import json

import pytest

from scenevoice.synth.load_plan import load_plan
from scenevoice.synth.plan_scene import PlanScene
from scenevoice.validation import Violation


def plan(*scenes):
    return json.dumps({"scenes": list(scenes)}).encode("utf-8")


def scene(ordinal=1, title="t", body="b"):
    return {"ordinal": ordinal, "title": title, "body": body}


def raw(ordinal_token="1", title='"t"', body='"b"'):
    return (
        f'{{"scenes":[{{"ordinal":{ordinal_token},"title":{title},"body":{body}}}]}}'
    ).encode()


@pytest.mark.parametrize(
    "data",
    [
        b"[]",
        b"1",
        b'"x"',
        b"null",
        b"true",
        b'{"scenes":[{"ordinal":1,"title":"t","body":"b"}],"extra":1}',
        b"{}",
        b'{"other":[]}',
        b'{"scenes":{}}',
        b'{"scenes":"x"}',
        b'{"scenes":null}',
        b'{"scenes":[]}',
        b'{"scenes":[1]}',
        b'{"scenes":[null]}',
        b'{"scenes":[[]]}',
        b'{"scenes":["x"]}',
        b'{"scenes":[{"title":"t","body":"b"}]}',
        b'{"scenes":[{"ordinal":1,"body":"b"}]}',
        b'{"scenes":[{"ordinal":1,"title":"t"}]}',
        b'{"scenes":[{"ordinal":1,"title":"t","body":"b","x":1}]}',
        b'{"scenes":[{"ordinal":1,"titel":"t","body":"b"}]}',
        b'{"scenes":[{"ordinal":1,"title":"t","text":"b"}]}',
        b'{"scenes":[{}]}',
    ],
)
def test_shape_rejections_are_violations(data):
    assert isinstance(load_plan(data), Violation)


@pytest.mark.parametrize(
    "token", ["true", "false", "1.0", "1e0", "1E0", "1.5", '"1"', "null", "[]", "{}", "-1"]
)
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


@pytest.mark.parametrize(
    "ordinals",
    [[0], [2], [0, 1], [1, 3], [1, 1], [1, 2, 2], [2, 1], [3, 2, 1], [1, 2, 4]],
)
def test_ordinal_sequence_rejected(ordinals):
    assert isinstance(load_plan(plan(*[scene(o) for o in ordinals])), Violation)


def test_later_scene_bool_ordinal_rejected():
    assert isinstance(load_plan(plan(scene(1), scene(True))), Violation)


@pytest.mark.parametrize("title", ["", "  ", "日本語 ü", "\u001c", "a\nb"])
def test_title_any_string_accepted(title):
    result = load_plan(plan(scene(title=title)))
    assert result == [PlanScene(1, title, "b")]


@pytest.mark.parametrize("title", ["1", "null", "true", "[]", "{}", "1.5"])
def test_title_non_string_rejected(title):
    assert isinstance(load_plan(raw(title=title)), Violation)


@pytest.mark.parametrize("body", ["1", "null", "true", "[]", "{}", "1.5"])
def test_body_non_string_rejected(body):
    assert isinstance(load_plan(raw(body=body)), Violation)


@pytest.mark.parametrize("body", ["", " ", "   ", "\n", "\t\n ", "　", " 　 "])
def test_body_blank_rejected(body):
    assert isinstance(load_plan(plan(scene(body=body))), Violation)


@pytest.mark.parametrize("body", ["\u001c", "\u001c ", "a", " a ", "　x"])
def test_body_non_blank_accepted(body):
    assert load_plan(plan(scene(body=body))) == [PlanScene(1, "t", body)]


def test_body_with_lone_surrogate_is_violation_not_exception():
    result = load_plan(raw(body='"\\ud800"'))
    assert isinstance(result, Violation)


def test_body_with_surrogate_among_text_is_violation():
    assert isinstance(load_plan(raw(body='"ok \\udfff ok"')), Violation)


def test_title_with_lone_surrogate_accepted():
    result = load_plan(raw(title='"\\ud800"'))
    assert result == [PlanScene(1, "\ud800", "b")]


def test_paired_surrogate_escape_in_body_accepted():
    assert load_plan(raw(body='"\\ud83d\\ude00"')) == [PlanScene(1, "t", "\U0001f600")]
