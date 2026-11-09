from scenevoice.pack import LINE_MARKER_COLOR, SCENE_MARKER_COLOR, line_marker


def test_marker_dict_has_marker2_keys_in_order():
    marker = line_marker(2, 3, "Third sentence.", 120)
    assert list(marker) == [
        "OTIO_SCHEMA",
        "metadata",
        "name",
        "color",
        "comment",
        "marked_range",
    ]
    assert marker["OTIO_SCHEMA"] == "Marker.2"
    assert marker["metadata"] == {}


def test_name_colour_comment_and_one_frame_range_at_rate_24():
    marker = line_marker(2, 3, "Third sentence.", 120)
    assert marker["name"] == "L2.3: Third sentence."
    assert marker["color"] == "GREEN"
    assert marker["comment"] == "Third sentence."
    assert marker["marked_range"] == {
        "OTIO_SCHEMA": "TimeRange.1",
        "duration": {"OTIO_SCHEMA": "RationalTime.1", "rate": 24, "value": 1},
        "start_time": {"OTIO_SCHEMA": "RationalTime.1", "rate": 24, "value": 120},
    }


def test_colour_constant_is_green_and_differs_from_scene_colour():
    assert LINE_MARKER_COLOR == "GREEN"
    assert LINE_MARKER_COLOR != SCENE_MARKER_COLOR
