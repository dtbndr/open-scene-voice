"""load_scenes wiring: each stage's violation is returned as is, and the stages run in order.

Messages and line numbers belong to the owning units (decode_script, check_cr,
check_controls, parse_scenes) and are pinned there.

validate_script returns only the violation (or None); scenes are discarded.

Rule outcomes belong to load_scenes and the units below it.
"""

import dataclasses
import sys

import pytest
from paths_helper import REPO_ROOT as ROOT

from scenevoice.validation import Violation, is_blank, load_scenes, validate_script
from scenevoice.validation.check_cr import check_cr
from scenevoice.validation.decode_script import decode_script
from scenevoice.validation.scene import Scene


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
    assert result.message == "This line ends in a Windows-style line break. Save the script with normal line endings."


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


@pytest.mark.parametrize(
    "text",
    [
        "hello\nworld\n",
        "café naïve\n",
        "你好世界\n",
        "party \U0001f389\n",
        "",
        "a\r\nb\rc\n",
        "a\n\ufeffb\n",
    ],
)
def test_valid_text_decodes_exactly(text):
    assert decode_script(text.encode("utf-8")) == text


@pytest.mark.parametrize("data", [b"\xef\xbb\xbf", b"\xef\xbb\xbfhello\n", b"\xef\xbb\xbf\xff\n"])
def test_initial_bom_is_reported_on_line_1(data):
    result = decode_script(data)
    assert isinstance(result, Violation)
    assert result.rule == "bom"
    assert result.line == 1
    assert result.message == (
        "The file starts with a hidden marker. Save it as plain UTF-8 text without a byte order mark."
    )


@pytest.mark.parametrize(
    "data, line",
    [
        (b"a\nb\nc\xff\n", 3),
        (b"a\n\xe2\x82", 2),
        (b"a\n\xe2\x82\nb\n", 2),
        (b"\x80", 1),
        (b"a\n\xed\xa0\x80\n", 2),
        (b"a\n\xef\xbb\xbfb\n\xff", 3),
    ],
)
def test_invalid_utf8_reports_line_of_first_bad_byte(data, line):
    result = decode_script(data)
    assert isinstance(result, Violation)
    assert result.rule == "invalid-utf8"
    assert result.line == line
    assert result.message == "The file is not plain UTF-8 text. Re-save it as UTF-8."


# Unicode White_Space property, written out explicitly (not derived from isspace()).
_WHITE_SPACE = frozenset(
    [*range(0x0009, 0x000E), 0x0020, 0x0085, 0x00A0, 0x1680]
    + [*range(0x2000, 0x200B), 0x2028, 0x2029, 0x202F, 0x205F, 0x3000]
)


_WHITE_SPACE_SORTED = sorted(_WHITE_SPACE)


# str.isspace() also accepts these four Cc controls; White_Space does not. They are
# rejected before is_blank sees text: test_check_controls pins that once.
_ISSPACE_EXTRAS = range(0x1C, 0x20)


_ACTUAL = {cp: is_blank(chr(cp)) for cp in range(sys.maxunicode + 1) if cp not in _ISSPACE_EXTRAS}


def test_empty_string_is_blank():
    assert is_blank("") is True


def test_mixed_and_repeated_white_space_is_blank():
    assert is_blank("".join(chr(cp) for cp in _WHITE_SPACE_SORTED)) is True
    assert all(is_blank(chr(cp) * 3) for cp in _WHITE_SPACE_SORTED)


@pytest.mark.parametrize(
    "text",
    ["\u200b", "\ufeff", "a", "0"],
    ids=["zwsp", "feff", "a", "0"],
)
def test_non_white_space_is_not_blank(text):
    assert is_blank(text) is False


@pytest.mark.parametrize("extra", ["a", "\u200b", "\ufeff"])
def test_white_space_plus_one_other_code_point_is_not_blank(extra):
    assert is_blank(" \t\u00a0\u3000" + extra + "\u2028") is False


def test_matches_explicit_white_space_list_across_all_code_points():
    # Each single code point is checked here, so no per-code-point test is needed.
    blank = {cp for cp, result in _ACTUAL.items() if result}
    assert blank == _WHITE_SPACE


def test_sample_script_returns_scenes_with_fields():
    scenes = load_scenes((ROOT / "sample/scripts/short.md").read_bytes())
    assert not isinstance(scenes, Violation)
    assert [(s.ordinal, s.title, s.line) for s in scenes] == [
        (1, "Scene 1: The Opening Hook", 9),
        (2, "Scene 2: The Plague", 12),
        (3, "Scene 3: War on the Danube", 15),
        (4, "Scene 4: Philosophy in the Trenches", 18),
        (5, "Scene 5: The Lesson", 21),
    ]
    assert scenes[0].body.startswith("Rome was burning")
    assert scenes[0].body.endswith("notebook instead.\n\n")


@pytest.mark.parametrize(
    "data, rule, line",
    [
        (b"\xef\xbb\xbfno marker here\n", "bom", 1),
        (b"## A\n\n\xff\n", "invalid-utf8", 3),
        (b"## A\r\n\n", "cr", 1),
        (b"## \n\tbody\n", "control", 2),
        (b"# Title\n\nsome text\n", "no-marker", None),
        (b"## \nbody\n", "blank-title", 1),
        (b"## A\ntext\n## B\n", "blank-body", 3),
    ],
    ids=["bom", "invalid-utf8", "cr", "control", "no-marker", "blank-title", "blank-body"],
)
def test_each_stage_violation_is_returned(data, rule, line):
    result = load_scenes(data)
    assert isinstance(result, Violation)
    assert (result.rule, result.line) == (rule, line)


@pytest.mark.parametrize(
    "data, line",
    [(b"a\r\n\tb\n", 1), (b"a\n\tb\nc\r\n", 3)],
    ids=["cr-first", "control-earlier-in-file"],
)
def test_cr_is_checked_before_controls(data, line):
    result = load_scenes(data)
    assert isinstance(result, Violation)
    assert (result.rule, result.line) == ("cr", line)


def test_scene_holds_fields():
    scene = Scene(ordinal=1, title="Arrival", body="Hi.\n", line=3)
    assert (scene.ordinal, scene.title, scene.body, scene.line) == (1, "Arrival", "Hi.\n", 3)


def test_scene_is_frozen():
    scene = Scene(1, "Arrival", "Hi.\n", 3)
    with pytest.raises(dataclasses.FrozenInstanceError):
        scene.title = "Other"  # type: ignore[misc]


def test_scenes_with_equal_fields_are_equal():
    assert Scene(1, "A", "b\n", 2) == Scene(1, "A", "b\n", 2)
    assert Scene(1, "A", "b\n", 2) != Scene(2, "A", "b\n", 2)


def test_violation_line_defaults_to_none():
    v = Violation(rule="r", message="m")
    assert (v.rule, v.message, v.line) == ("r", "m", None)


def test_violation_line_is_kept_when_given():
    assert Violation(rule="r", message="m", line=3).line == 3


def test_violation_is_immutable():
    v = Violation(rule="r", message="m")
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.message = "other"  # type: ignore[misc]


@pytest.mark.parametrize("name", ["sample/scripts/short.md", "sample/scripts/long.md"])
def test_valid_sample_scripts_return_none(name):
    assert validate_script((ROOT / name).read_bytes()) is None


def test_multibyte_script_returns_none():
    assert validate_script("## T\ncafé 你好 \U0001f389\n".encode("utf-8")) is None


@pytest.mark.parametrize(
    "data, rule, line",
    [
        (b"", "no-marker", None),
        (b"\xef\xbb\xbfhello\n", "bom", 1),
        (b"a\nb\nc\xff\n", "invalid-utf8", 3),
        (b"a\nb\nc\r\nd\n", "cr", 3),
        (b"a\n\tb\n", "control", 2),
        (b"## A\ntext\n## B\n", "blank-body", 3),
    ],
    ids=["empty", "bom", "invalid-utf8", "cr", "control", "blank-body"],
)
def test_violation_is_returned(data, rule, line):
    result = validate_script(data)
    assert result is not None
    assert (result.rule, result.line) == (rule, line)
