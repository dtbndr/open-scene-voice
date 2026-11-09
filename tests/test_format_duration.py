import pytest

from scenevoice.pack import format_duration


@pytest.mark.parametrize(
    ("frames", "expected"),
    [
        (1, "0.000"),
        (11, "0.000"),
        (12, "0.001"),
        (13, "0.001"),
        (35, "0.001"),
        (36, "0.002"),
        (37, "0.002"),
        (24000, "1.000"),
        (36000, "1.500"),
        (50400, "2.100"),
        (123456, "5.144"),
        (10_000_000, "416.667"),
        (10_000_012, "416.667"),
        (10_000_020, "416.668"),
        (24_000_012, "1000.001"),
    ],
)
def test_format_duration_table(frames, expected):
    result = format_duration(frames)
    assert result == expected
    assert isinstance(result, str)
    assert result.split(".")[1].__len__() == 3
