from typing import Any

from scenevoice.pack.time_range import time_range
from scenevoice.pack.timeline_constants import (
    FRAME_RATE,
    LINE_MARKER_COLOR,
    MARKER_FRAMES,
)


def line_marker(ordinal: int, number: int, text: str, frame: int) -> dict[str, Any]:
    return {
        "OTIO_SCHEMA": "Marker.2",
        "metadata": {},
        "name": f"L{ordinal}.{number}: {text}",
        "color": LINE_MARKER_COLOR,
        "comment": text,
        "marked_range": time_range(frame, MARKER_FRAMES, FRAME_RATE),
    }
