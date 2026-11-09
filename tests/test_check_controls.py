import sys
import unicodedata

import pytest

from scenevoice.validation.check_controls import check_controls
from scenevoice.validation.violation import Violation

_ALL_CC = [cp for cp in range(sys.maxunicode + 1) if unicodedata.category(chr(cp)) == "Cc"]
_REJECTED = [cp for cp in _ALL_CC if cp != 0x0A]


def _assert_control(result, line):
    assert isinstance(result, Violation)
    assert result.rule == "control"
    assert result.line == line
    assert result.message


@pytest.mark.parametrize(
    "char",
    [
        "\x00",
        "\t",
        "\x1b",
        "\x7f",
        "\x85",
        pytest.param("\r", id="cr-alone-is-rejected-by-check_controls"),
    ],
)
def test_control_character_is_rejected_on_line_1(char):
    _assert_control(check_controls(f"a{char}b\n"), 1)


@pytest.mark.parametrize(
    "text, line",
    [
        ("a\nb\n\tc\n", 3),
        ("a\nb\x00\n", 2),
        ("a\u2028b\u2029c\td\n", 1),
        ("a\u2028\nb\u2029\x85\n", 2),
        ("a\rb\n\tc\n", 1),
    ],
)
def test_first_control_reports_its_line(text, line):
    _assert_control(check_controls(text), line)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "a\nb\n",
        "\n\n",
        "a\u00a0b\n",
        "a\u3000b\n",
        "a\u200bb\n",
        "a\n\ufeffb\n",
        "a\u2028b\u2029c\n",
        "café naïve\n",
        "你好世界\n",
        "party \U0001f389\n",
    ],
)
def test_non_control_text_passes(text):
    assert check_controls(text) is None


def test_cc_set_has_65_code_points():
    assert len(_ALL_CC) == 65


def test_rejects_exactly_cc_except_lf():
    rejected = {cp for cp in range(sys.maxunicode + 1) if check_controls(chr(cp)) is not None}
    assert rejected == set(_REJECTED)
