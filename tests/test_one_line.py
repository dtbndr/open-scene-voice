import pytest

from scenevoice.synth import one_line


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a", "a"),
        ("a\nb", "a b"),
        ("a\r\nb", "a b"),
        ("a\rb", "a b"),
        ("a\n\r\n\rb", "a b"),
        ("a\nb\r\nc", "a b c"),
        ("end\n", "end "),
        ("", ""),
        ("a  b\tc", "a  b\tc"),
    ],
)
def test_one_line(text, expected):
    assert one_line(text) == expected
