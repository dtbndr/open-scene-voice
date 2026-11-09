import math


def seconds_to_ms(start: float) -> int | None:
    """Round seconds to whole milliseconds, half up; None if not representable."""
    try:
        scaled = start * 1000 + 0.5
        if not math.isfinite(scaled):
            return None
        return math.floor(scaled)
    except OverflowError:
        return None
