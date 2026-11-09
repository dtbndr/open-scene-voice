from typing import Any

from scenevoice.pack.rational_time import rational_time


def time_range(start: int, duration: int, rate: int) -> dict[str, Any]:
    return {
        "OTIO_SCHEMA": "TimeRange.1",
        "duration": rational_time(duration, rate),
        "start_time": rational_time(start, rate),
    }
