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
    ],
)
def test_first_control_reports_its_line(text, line):
    _assert_control(check_controls(text), line)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "a\nb\n",
        "a\u00a0b\n",
        "a\u200bb\n",
        "café naïve\n",
    ],
)
def test_non_control_text_passes(text):
    assert check_controls(text) is None


@pytest.mark.parametrize("char, code", [("\t", "0009"), ("\x1b", "001B"), ("\x7f", "007F"), ("\x85", "0085")])
def test_message_names_the_code_as_four_digit_uppercase_hex(char, code):
    result = check_controls(f"a{char}b\n")
    assert result is not None
    assert result.message == f"This line has a hidden character that cannot be spoken (U+{code}). Delete it."


def test_cc_set_has_65_code_points():
    assert len(_ALL_CC) == 65


def test_rejects_exactly_cc_except_lf():
    # Includes U+001C-U+001F, which str.isspace() accepts: they must never reach is_blank.
    rejected = {cp for cp in range(sys.maxunicode + 1) if check_controls(chr(cp)) is not None}
    assert rejected == set(_REJECTED)
