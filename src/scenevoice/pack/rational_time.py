from typing import Any


def rational_time(value: int, rate: int) -> dict[str, Any]:
    return {"OTIO_SCHEMA": "RationalTime.1", "rate": rate, "value": value}
