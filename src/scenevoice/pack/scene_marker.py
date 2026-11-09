from typing import Any

from scenevoice.pack.time_range import time_range
from scenevoice.pack.timeline_constants import (
    FRAME_RATE,
    MARKER_FRAMES,
    SCENE_MARKER_COLOR,
)
from scenevoice.synth import PlanScene


def scene_marker(scene: PlanScene, frame: int) -> dict[str, Any]:
    name = f"Scene {scene.ordinal}"
    if scene.title != "":
        name = f"{name}: {scene.title}"
    return {
        "OTIO_SCHEMA": "Marker.2",
        "metadata": {},
        "name": name,
        "color": SCENE_MARKER_COLOR,
        "comment": scene.body,
        "marked_range": time_range(frame, MARKER_FRAMES, FRAME_RATE),
    }
