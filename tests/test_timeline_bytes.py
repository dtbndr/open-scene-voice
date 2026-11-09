import json

import pytest

from scenevoice.pack import build_timeline
from scenevoice.synth import PlanScene


def _build(scenes, frames):
    return build_timeline(scenes, frames)[0]


def _doc(scenes, frames):
    return json.loads(_build(scenes, frames))


def _two():
    return [PlanScene(1, "A", "a"), PlanScene(2, "B", "b")]


def test_structure_values():
    doc = _doc(_two(), [50400, 123456])
    assert doc["OTIO_SCHEMA"] == "Timeline.1"
    assert doc["name"] == "SceneVoice"
    assert doc["global_start_time"]["value"] == 0
    assert doc["global_start_time"]["rate"] == 24
    stack = doc["tracks"]
    assert stack["name"] == "tracks"
    assert len(stack["children"]) == 1
    track = stack["children"][0]
    assert track["name"] == "Narration"
    assert track["kind"] == "Audio"
    assert track["enabled"] is True
    assert [c["OTIO_SCHEMA"] for c in track["children"]] == [
        "Clip.1", "Gap.1", "Clip.1",
    ]
    marks = stack["markers"]
    assert [m["marked_range"]["start_time"]["value"] for m in marks] == [0, 60]


def test_key_orders():
    doc = _doc(_two(), [50400, 123456])
    assert list(doc) == [
        "OTIO_SCHEMA", "metadata", "name", "global_start_time", "tracks",
    ]
    stack = doc["tracks"]
    assert list(stack) == [
        "OTIO_SCHEMA", "metadata", "name", "source_range", "effects",
        "markers", "enabled", "children",
    ]
    track = stack["children"][0]
    assert list(track) == [
        "OTIO_SCHEMA", "metadata", "name", "source_range", "effects",
        "markers", "enabled", "children", "kind",
    ]
    assert list(track["children"][0]) == [
        "OTIO_SCHEMA", "metadata", "name", "source_range", "effects",
        "markers", "media_reference",
    ]


def test_byte_hygiene():
    raw = _build(_two(), [50400, 123456])
    text = raw.decode("ascii")
    assert text.endswith("}\n")
    assert not text.endswith("\n\n")
    assert "\r" not in text
    assert "\t" not in text
    assert not any(line.endswith(", ") for line in text.split("\n"))


def test_rate_and_value_are_integers():
    raw = _build(_two(), [50400, 123456]).decode("ascii")
    lines = [
        ln for ln in raw.split("\n") if '"rate":' in ln or '"value":' in ln
    ]
    assert lines
    assert all("." not in ln for ln in lines)


def test_single_scene():
    doc = _doc([PlanScene(1, "A", "a")], [5000])
    track = doc["tracks"]["children"][0]
    assert [c["OTIO_SCHEMA"] for c in track["children"]] == ["Clip.1"]
    marks = doc["tracks"]["markers"]
    assert len(marks) == 1
    assert marks[0]["marked_range"]["start_time"]["value"] == 0


def _start(obj):
    return obj["marked_range"]["start_time"]["value"]


def test_three_scene_arithmetic():
    scenes = [PlanScene(1, "A", ""), PlanScene(2, "B", ""), PlanScene(3, "C", "")]
    doc = _doc(scenes, [10000, 20000, 30000])
    children = doc["tracks"]["children"][0]["children"]
    assert [c["OTIO_SCHEMA"] for c in children] == [
        "Clip.1", "Gap.1", "Clip.1", "Gap.1", "Clip.1",
    ]
    assert [c["name"] for c in children if c["OTIO_SCHEMA"] == "Clip.1"] == [
        "Scene 1", "Scene 2", "Scene 3",
    ]
    assert [_start(m) for m in doc["tracks"]["markers"]] == [0, 20, 50]


def test_minimum_length_clip_between_scenes():
    scenes = [PlanScene(1, "A", ""), PlanScene(2, "B", ""), PlanScene(3, "C", "")]
    doc = _doc(scenes, [5000, 1000, 7000])
    assert [_start(m) for m in doc["tracks"]["markers"]] == [0, 15, 26]
    clip = doc["tracks"]["children"][0]["children"][2]
    assert clip["source_range"]["duration"]["value"] == 1


def test_empty_title_name():
    doc = _doc([PlanScene(4, "", "x")], [2000])
    assert doc["tracks"]["markers"][0]["name"] == "Scene 4"


def test_escapes_in_text():
    body = "a\nb\rc\td\be\ff\"g\\h/i\x01j\x7fké中\U0001F600"
    raw = _build([PlanScene(1, "T", body)], [2000]).decode("ascii")
    expected = (
        '"comment": "a\\nb\\rc\\td\\be\\ff\\"g\\\\h/i\\u0001j\\u007fk'
        '\\u00e9\\u4e2d\\ud83d\\ude00"'
    )
    assert expected in raw


def test_empty_body():
    raw = _build([PlanScene(1, "T", "")], [2000]).decode("ascii")
    assert '"comment": ""' in raw


def test_deterministic_and_no_mutation():
    scenes = _two()
    frames = [50400, 123456]
    first = build_timeline(scenes, frames)[0]
    assert build_timeline(scenes, frames)[0] == first
    assert scenes == _two()
    assert frames == [50400, 123456]


def test_ordinal_used_verbatim():
    raw = _build([PlanScene(7, "T", "b")], [2000]).decode("ascii")
    assert '"name": "Scene 7"' in raw
    assert '"target_url": "audio/007.wav"' in raw
    assert '"name": "Scene 7: T"' in raw


@pytest.mark.parametrize("frames", [[1000], [999999]])
def test_returns_bytes(frames):
    assert isinstance(_build([PlanScene(1, "T", "b")], frames), bytes)
