from scenevoice.align import SceneTimings, serialize_timings
from scenevoice.pack import LineTiming, parse_line_timings

H1 = "0" * 64
H2 = "f" * 64


def test_serializer_output_parses_to_the_same_lines():
    scenes = [
        SceneTimings(1, H1, [LineTiming("Hello.", 0), LineTiming("Miss.", None)]),
        SceneTimings(2, H2, [LineTiming('Café "quoted"   \U0001f600', 1234)]),
        SceneTimings(3, H1, []),
    ]
    table = parse_line_timings(serialize_timings(scenes))
    assert table == {s.ordinal: (s.sha256, s.lines) for s in scenes}


def test_empty_scene_list_round_trips():
    assert parse_line_timings(serialize_timings([])) == {}
