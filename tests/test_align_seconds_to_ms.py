import math

import pytest

from scenevoice.align import seconds_to_ms


@pytest.mark.parametrize(
    ("start", "expected"),
    [
        (0.23999999865889549, 240),
        (1.2344, 1234),
        (1.2346, 1235),
        (0, 0),
        (0.0, 0),
        (-0.0, 0),
        (2, 2000),
        (1.86, 1860),
    ],
)
def test_milliseconds(start: float, expected: int) -> None:
    result = seconds_to_ms(start)
    assert result == expected
    assert type(result) is int


@pytest.mark.parametrize(
    "start", [10**400, math.inf, -math.inf, math.nan, 1e308]
)
def test_overflow_and_non_finite_return_none(start: float) -> None:
    assert seconds_to_ms(start) is None
