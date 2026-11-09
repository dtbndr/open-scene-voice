import pytest

from scenevoice.pack import (
    FRAME_RATE,
    MARKER_FRAMES,
    PAUSE_FRAMES,
    SAMPLE_FRAMES_PER_TIMELINE_FRAME,
    SAMPLE_RATE,
    TIMELINE_NAME,
    clip_entry,
    clip_frames,
    gap_entry,
    rational_time,
    time_range,
)
from scenevoice.synth import PlanScene


def _no_floats(node):
    if isinstance(node, dict):
        for value in node.values():
            _no_floats(value)
    elif isinstance(node, list):
        for value in node:
            _no_floats(value)
    else:
        assert not isinstance(node, (float, bool))


def test_constants():
    assert TIMELINE_NAME == "resolve_timeline.otio"
    assert FRAME_RATE == 24
    assert SAMPLE_RATE == 24000
    assert PAUSE_FRAMES == 10
    assert MARKER_FRAMES == 1
    assert SAMPLE_FRAMES_PER_TIMELINE_FRAME == 1000


@pytest.mark.parametrize(
    ("wav_frames", "expected"),
    [(50400, 50), (123456, 123), (1000, 1), (1999, 1), (999, 0), (24000, 24), (10**18 - 1, 10**15 - 1)],
)
def test_clip_frames_floors(wav_frames, expected):
    result = clip_frames(wav_frames)
    assert result == expected
    assert type(result) is int


def test_rational_time():
    value = rational_time(5, 24)
    assert list(value) == ["OTIO_SCHEMA", "rate", "value"]
    assert value == {"OTIO_SCHEMA": "RationalTime.1", "rate": 24, "value": 5}


def test_time_range():
    value = time_range(3, 7, 24)
    assert list(value) == ["OTIO_SCHEMA", "duration", "start_time"]
    assert value["OTIO_SCHEMA"] == "TimeRange.1"
    assert value["duration"] == rational_time(7, 24)
    assert value["start_time"] == rational_time(3, 24)
    _no_floats(value)


def test_gap_entry():
    gap = gap_entry()
    assert list(gap) == [
        "OTIO_SCHEMA", "metadata", "name", "source_range", "effects", "markers",
    ]
    assert gap["OTIO_SCHEMA"] == "Gap.1"
    assert gap["metadata"] == {}
    assert gap["name"] == ""
    assert gap["source_range"] == time_range(0, 10, 24)
    assert gap["effects"] == []
    assert gap["markers"] == []
    _no_floats(gap)


def test_gap_entries_are_independent():
    gap_entry()["markers"].append(1)
    assert gap_entry()["markers"] == []


def test_clip_entry():
    clip = clip_entry(PlanScene(7, "T", "B"), 50400)
    assert list(clip) == [
        "OTIO_SCHEMA", "metadata", "name", "source_range", "effects", "markers",
        "media_reference",
    ]
    assert clip["OTIO_SCHEMA"] == "Clip.1"
    assert clip["metadata"] == {}
    assert clip["name"] == "Scene 7"
    assert clip["source_range"] == time_range(0, 50, 24)
    assert clip["effects"] == []
    assert clip["markers"] == []
    ref = clip["media_reference"]
    assert list(ref) == [
        "OTIO_SCHEMA", "metadata", "name", "available_range", "target_url",
    ]
    assert ref["OTIO_SCHEMA"] == "ExternalReference.1"
    assert ref["metadata"] == {}
    assert ref["name"] == ""
    assert ref["available_range"] == time_range(0, 50400, 24000)
    assert ref["target_url"] == "audio/007.wav"
    _no_floats(clip)


def test_clip_entry_floors_source_range_keeps_full_available_range():
    clip = clip_entry(PlanScene(12, "", ""), 123456)
    assert clip["source_range"]["duration"]["value"] == 123
    assert clip["media_reference"]["available_range"]["duration"]["value"] == 123456
    assert clip["media_reference"]["target_url"] == "audio/012.wav"
