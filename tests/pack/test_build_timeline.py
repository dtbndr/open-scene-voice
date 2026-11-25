import copy
import json

from paths_helper import FIXTURES

from scenevoice.pack import LineTiming, build_timeline, skipped_marker_note
from scenevoice.synth import PlanScene

GOLDEN = FIXTURES / "resolve_timeline_two_scenes.otio"
LINE_GOLDEN = FIXTURES / "resolve_timeline_line_markers.otio"


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


# Golden bytes (hand-verified in Resolve in WS23 and WS25; the fixtures must not change)


def _cafe_scenes():
    return [
        PlanScene(1, "Café, au lait", "First sentence."),
        PlanScene(2, 'The "big" day', "Second sentence."),
    ]


def _cafe_timings():
    return {
        1: [
            LineTiming("First sentence.", 0),
            LineTiming("Second sentence.", 1000),
            LineTiming("Third sentence.", 2120),
        ],
        2: [LineTiming("Fourth sentence.", 2500)],
    }


def test_two_scene_timeline_matches_hand_written_golden_bytes():
    data, skipped = build_timeline(_cafe_scenes(), [50400, 123456])
    assert data == GOLDEN.read_bytes()
    assert skipped == []
    assert build_timeline(_cafe_scenes(), [50400, 123456], None)[0] == data


def test_worked_example_matches_hand_written_line_marker_golden_bytes():
    data, skipped = build_timeline(_cafe_scenes(), [50400, 123456], _cafe_timings())
    assert data == LINE_GOLDEN.read_bytes()
    assert skipped == []


def test_scene_absent_from_timings_and_empty_lines_keep_scene_marker_only():
    data = build_timeline(_cafe_scenes(), [50400, 123456], {1: []})[0]
    assert data == GOLDEN.read_bytes()


def test_1500_frame_skip_case():
    plan = [PlanScene(1, "T", "b")]
    data, skipped = build_timeline(plan, [1500], {1: [LineTiming("Hi.", 0)]})
    assert skipped == [(1, 1)]
    assert skipped_marker_note(*skipped[0]) == (
        "scenevoice pack: NOTE scene 1 line 1: marker skipped, no free frame"
    )
    assert len(json.loads(data)["tracks"]["markers"]) == 1


def test_skipped_order_is_plan_then_line_order():
    plan = [PlanScene(1, "T", "b")]
    lines = [LineTiming("a", 0), LineTiming("b", 1000), LineTiming("c", 0)]
    data, skipped = build_timeline(plan, [2000], {1: lines})
    assert skipped == [(1, 2), (1, 3)]
    assert [m["name"] for m in json.loads(data)["tracks"]["markers"]] == ["Scene 1: T", "L1.1: a"]


def test_null_start_keeps_number_and_makes_no_marker():
    plan = [PlanScene(1, "T", "b")]
    lines = [LineTiming("a", None), LineTiming("b", 1000)]
    data, _ = build_timeline(plan, [50400], {1: lines})
    names = [m["name"] for m in json.loads(data)["tracks"]["markers"]]
    assert names == ["Scene 1: T", "L1.2: b"]


def test_inputs_are_not_mutated_and_output_is_deterministic():
    plan, tm = _cafe_scenes(), _cafe_timings()
    before = (copy.deepcopy(plan), copy.deepcopy(tm))
    first = build_timeline(plan, [50400, 123456], tm)
    assert build_timeline(plan, [50400, 123456], tm) == first
    assert (plan, tm) == before
