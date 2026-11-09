from typing import Any

from scenevoice.pack.time_range import time_range
from scenevoice.pack.timeline_constants import FRAME_RATE, PAUSE_FRAMES


def gap_entry() -> dict[str, Any]:
    return {
        "OTIO_SCHEMA": "Gap.1",
        "metadata": {},
        "name": "",
        "source_range": time_range(0, PAUSE_FRAMES, FRAME_RATE),
        "effects": [],
        "markers": [],
    }
