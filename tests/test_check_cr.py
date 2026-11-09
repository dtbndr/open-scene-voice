import pytest

from scenevoice.validation.check_cr import check_cr
from scenevoice.validation.violation import Violation


@pytest.mark.parametrize("text", ["", "a\nb\nc\n", "no newline", "café\n你好\n"])
def test_text_without_cr_passes(text):
    assert check_cr(text) is None


@pytest.mark.parametrize(
    "text, line",
    [
        ("a\r\nb\r\n", 1),
        ("a\nb\nc\r\nd\r\n", 3),
        ("ab\rcd\n", 1),
        ("a\nb\nc\rd\n", 3),
        ("a\nb\r\nc\nd\r\n", 2),
    ],
)
def test_first_cr_is_reported_with_its_line(text, line):
    result = check_cr(text)
    assert isinstance(result, Violation)
    assert result.rule == "cr"
    assert result.line == line
    assert result.message


@pytest.mark.parametrize(
    "text, line",
    [
        ("a\u2028b\u2029c\rd\n", 1),
        ("a\u2028\nb\u2029\r\n", 2),
    ],
)
def test_only_lf_advances_the_line(text, line):
    result = check_cr(text)
    assert isinstance(result, Violation)
    assert (result.rule, result.line) == ("cr", line)
