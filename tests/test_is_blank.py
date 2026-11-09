import sys

import pytest

from scenevoice.validation import is_blank
from scenevoice.validation.check_controls import check_controls

# Unicode White_Space property, written out explicitly (not derived from isspace()).
_WHITE_SPACE = frozenset(
    [*range(0x0009, 0x000E), 0x0020, 0x0085, 0x00A0, 0x1680]
    + [*range(0x2000, 0x200B), 0x2028, 0x2029, 0x202F, 0x205F, 0x3000]
)
_WHITE_SPACE_SORTED = sorted(_WHITE_SPACE)

# str.isspace() also accepts these four Cc controls; White_Space does not.
_ISSPACE_EXTRAS = range(0x1C, 0x20)

_ACTUAL = {cp: is_blank(chr(cp)) for cp in range(sys.maxunicode + 1) if cp not in _ISSPACE_EXTRAS}


def test_empty_string_is_blank():
    assert is_blank("") is True


@pytest.mark.parametrize("cp", _WHITE_SPACE_SORTED, ids=lambda cp: f"U+{cp:04X}")
def test_each_white_space_code_point_is_blank(cp):
    assert is_blank(chr(cp)) is True
    assert is_blank(chr(cp) * 3) is True


def test_mixed_white_space_is_blank():
    assert is_blank("".join(chr(cp) for cp in _WHITE_SPACE_SORTED)) is True


@pytest.mark.parametrize(
    "text",
    ["\u200b", "\u180e", "\ufeff", "a", "Z", "0", "9", ".", "-", "你"],
    ids=["zwsp", "mongolian-vowel-separator", "feff", "a", "Z", "0", "9", "dot", "dash", "cjk"],
)
def test_non_white_space_is_not_blank(text):
    assert is_blank(text) is False


@pytest.mark.parametrize("extra", ["a", "\u200b", "\ufeff"])
def test_white_space_plus_one_other_code_point_is_not_blank(extra):
    assert is_blank(" \t\u00a0\u3000" + extra + "\u2028") is False


def test_matches_explicit_white_space_list_across_all_code_points():
    blank = {cp for cp, result in _ACTUAL.items() if result}
    assert blank == _WHITE_SPACE


@pytest.mark.parametrize("cp", _ISSPACE_EXTRAS, ids=lambda cp: f"U+{cp:04X}")
def test_isspace_extras_are_rejected_by_check_controls(cp):
    # isspace() also treats U+001C-001F as whitespace, but they are Cc controls
    # that check_controls rejects before any later step, so is_blank never sees them.
    assert check_controls(f"a{chr(cp)}b\n") is not None
