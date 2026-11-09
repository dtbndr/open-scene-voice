import pytest

from scenevoice.pack import scene_marker, time_range
from scenevoice.synth import PlanScene


def test_marker_shape():
    marker = scene_marker(PlanScene(2, "Hello", "Body"), 34)
    assert list(marker) == [
        "OTIO_SCHEMA", "metadata", "name", "color", "comment", "marked_range",
    ]
    assert marker["OTIO_SCHEMA"] == "Marker.2"
    assert marker["metadata"] == {}
    assert marker["color"] == "BLUE"
    assert marker["name"] == "Scene 2: Hello"
    assert marker["comment"] == "Body"
    assert marker["marked_range"] == time_range(34, 1, 24)


def test_empty_title_has_no_colon_or_space():
    assert scene_marker(PlanScene(1, "", "b"), 0)["name"] == "Scene 1"


@pytest.mark.parametrize(
    "title",
    [" lead", "trail ", "Scene 9: inner", "a: b", "café 中", "   "],
)
def test_title_verbatim(title):
    assert scene_marker(PlanScene(3, title, ""), 0)["name"] == f"Scene 3: {title}"


@pytest.mark.parametrize("body", ["", "line1\nline2", 'say "hi"', "café 中"])
def test_body_verbatim(body):
    assert scene_marker(PlanScene(1, "t", body), 0)["comment"] == body


def test_frame_is_an_int_start():
    start = scene_marker(PlanScene(1, "t", ""), 60)["marked_range"]["start_time"]
    assert start == {"OTIO_SCHEMA": "RationalTime.1", "rate": 24, "value": 60}
