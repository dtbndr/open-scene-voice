import json

from scenevoice.plan import serialize_plan
from scenevoice.validation.scene import Scene


def test_top_level_and_scene_key_sets():
    scenes = [Scene(ordinal=1, title="A", body="b", line=3)]
    data = json.loads(serialize_plan(scenes))
    assert set(data) == {"scenes"}
    assert set(data["scenes"][0]) == {"ordinal", "title", "body"}


def test_ordinal_comes_from_the_scene_not_the_title():
    scenes = [
        Scene(ordinal=1, title="Scene 1: one", body="a", line=1),
        Scene(ordinal=2, title="Scene 4: two", body="b", line=4),
        Scene(ordinal=5, title="Scene 6: five", body="c", line=9),
    ]
    data = json.loads(serialize_plan(scenes))
    assert [s["ordinal"] for s in data["scenes"]] == [1, 2, 5]
    assert data["scenes"][2]["title"] == "Scene 6: five"


def test_line_never_serialized():
    out = serialize_plan([Scene(ordinal=1, title="t", body="b", line=42)])
    assert "line" not in json.loads(out)["scenes"][0]
    assert '"line"' not in out


def test_non_ascii_written_unescaped():
    title = "caf\u00e9"
    body = "a\u2028b\u200bc"
    out = serialize_plan([Scene(ordinal=1, title=title, body=body, line=1)])
    assert title in out
    assert "a\u2028b\u200bc" in out
    assert "\\u" not in out


def test_only_required_escapes_present():
    scene = Scene(ordinal=1, title='say "hi" \\ there', body="x\ny", line=1)
    out = serialize_plan([scene])
    assert '\\"hi\\"' in out
    assert "\\\\" in out
    assert "\\n" in out
    assert "\\u" not in out
    assert "\n" not in out[:-1]


def test_exactly_one_trailing_lf():
    out = serialize_plan([Scene(ordinal=1, title="t", body="b\n", line=1)])
    assert out.endswith("\n")
    assert not out.endswith("\n\n")
    assert out.count("\n") == 1


def test_round_trip_preserves_source_order_and_text():
    scenes = [
        Scene(ordinal=1, title="one", body="a\nb", line=1),
        Scene(ordinal=2, title="two", body="", line=5),
    ]
    assert json.loads(serialize_plan(scenes)) == {
        "scenes": [
            {"ordinal": 1, "title": "one", "body": "a\nb"},
            {"ordinal": 2, "title": "two", "body": ""},
        ]
    }
