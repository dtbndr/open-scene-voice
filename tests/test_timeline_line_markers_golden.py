import copy
import json
from pathlib import Path

from scenevoice.pack import LineTiming, build_timeline, skipped_marker_note
from scenevoice.synth import PlanScene

FIXTURES = Path(__file__).parent / "fixtures"
LINE_GOLDEN = FIXTURES / "resolve_timeline_line_markers.otio"
WS23_GOLDEN = FIXTURES / "resolve_timeline_two_scenes.otio"


def scenes():
    return [
        PlanScene(1, "Café, au lait", "First sentence."),
        PlanScene(2, 'The "big" day', "Second sentence."),
    ]


def timings():
    return {
        1: [
            LineTiming("First sentence.", 0),
            LineTiming("Second sentence.", 1000),
            LineTiming("Third sentence.", 2120),
        ],
        2: [LineTiming("Fourth sentence.", 2500)],
    }


def test_worked_example_matches_hand_written_golden_bytes():
    data, skipped = build_timeline(scenes(), [50400, 123456], timings())
    assert data == LINE_GOLDEN.read_bytes()
    assert skipped == []


def test_final_marker_frames_and_colours():
    data, _ = build_timeline(scenes(), [50400, 123456], timings())
    markers = json.loads(data)["tracks"]["markers"]
    assert [m["marked_range"]["start_time"]["value"] for m in markers] == [0, 1, 24, 49, 60, 120]
    assert [m["color"] for m in markers] == ["BLUE", "GREEN", "GREEN", "GREEN", "BLUE", "GREEN"]


def test_timings_none_equals_ws23_golden():
    data, skipped = build_timeline(scenes(), [50400, 123456])
    assert data == WS23_GOLDEN.read_bytes()
    assert skipped == []
    assert build_timeline(scenes(), [50400, 123456], None)[0] == data


def test_scene_absent_from_timings_and_empty_lines_keep_scene_marker_only():
    data = build_timeline(scenes(), [50400, 123456], {1: []})[0]
    assert data == WS23_GOLDEN.read_bytes()


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
    plan, tm = scenes(), timings()
    before = (copy.deepcopy(plan), copy.deepcopy(tm))
    first = build_timeline(plan, [50400, 123456], tm)
    assert build_timeline(plan, [50400, 123456], tm) == first
    assert (plan, tm) == before
