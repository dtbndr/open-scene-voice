import json
from collections.abc import Mapping
from typing import Any

from scenevoice.pack.clip_entry import clip_entry
from scenevoice.pack.clip_frames import clip_frames
from scenevoice.pack.gap_entry import gap_entry
from scenevoice.pack.line_marker import line_marker
from scenevoice.pack.line_timing import LineTiming
from scenevoice.pack.place_markers import place_markers
from scenevoice.pack.rational_time import rational_time
from scenevoice.pack.scene_marker import scene_marker
from scenevoice.pack.timeline_constants import (
    FRAME_RATE,
    PAUSE_FRAMES,
    STACK_NAME,
    TIMELINE_TITLE,
    TRACK_NAME,
)
from scenevoice.synth import PlanScene


def build_timeline(
    scenes: list[PlanScene],
    frames: list[int],
    timings: Mapping[int, list[LineTiming]] | None = None,
) -> tuple[bytes, list[tuple[int, int]]]:
    """Return the timeline bytes and the skipped (scene ordinal, line number) pairs.

    timings holds fresh line data only; a scene without an entry gets its scene marker alone.
    """
    children: list[dict[str, Any]] = []
    spans: list[tuple[int, int, int, list[LineTiming]]] = []
    spans_lines: dict[int, list[LineTiming]] = {}
    start = 0
    for index, (scene, wav_frames) in enumerate(zip(scenes, frames, strict=True)):
        if index > 0:
            children.append(gap_entry())
            start += PAUSE_FRAMES
        children.append(clip_entry(scene, wav_frames))
        lines = [] if timings is None else timings.get(scene.ordinal, [])
        spans_lines[scene.ordinal] = lines
        spans.append((scene.ordinal, start, clip_frames(wav_frames), lines))
        start += clip_frames(wav_frames)
    placed, skipped = place_markers(spans)
    by_ordinal = {scene.ordinal: scene for scene in scenes}
    markers: list[dict[str, Any]] = []
    for frame, ordinal, number in placed:
        if number == 0:
            markers.append(scene_marker(by_ordinal[ordinal], frame))
        else:
            text = spans_lines[ordinal][number - 1].text
            markers.append(line_marker(ordinal, number, text, frame))
    track: dict[str, Any] = {
        "OTIO_SCHEMA": "Track.1",
        "metadata": {},
        "name": TRACK_NAME,
        "source_range": None,
        "effects": [],
        "markers": [],
        "enabled": True,
        "children": children,
        "kind": "Audio",
    }
    stack: dict[str, Any] = {
        "OTIO_SCHEMA": "Stack.1",
        "metadata": {},
        "name": STACK_NAME,
        "source_range": None,
        "effects": [],
        "markers": markers,
        "enabled": True,
        "children": [track],
    }
    timeline: dict[str, Any] = {
        "OTIO_SCHEMA": "Timeline.1",
        "metadata": {},
        "name": TIMELINE_TITLE,
        "global_start_time": rational_time(0, FRAME_RATE),
        "tracks": stack,
    }
    return (json.dumps(timeline, indent=2, ensure_ascii=True) + "\n").encode("ascii"), skipped
