from pathlib import Path

import pytest

from scenevoice.validation import validate_script

ROOT = Path(__file__).resolve().parent.parent


def test_empty_bytes_fail_with_no_marker():
    result = validate_script(b"")
    assert result is not None
    assert (result.rule, result.line) == ("no-marker", None)


@pytest.mark.parametrize("name", ["sample/scripts/short.md", "sample/scripts/long.md"])
def test_lexically_valid_sample_scripts(name):
    assert validate_script((ROOT / name).read_bytes()) is None


def test_lexically_valid_multibyte_text():
    assert validate_script("## T\ncafé 你好 \U0001f389\n".encode("utf-8")) is None


def test_bom_is_a_violation_on_line_1():
    result = validate_script(b"\xef\xbb\xbfhello\n")
    assert result is not None
    assert (result.rule, result.line) == ("bom", 1)


def test_invalid_utf8_is_a_violation_on_its_line():
    result = validate_script(b"a\nb\nc\xff\n")
    assert result is not None
    assert (result.rule, result.line) == ("invalid-utf8", 3)


@pytest.mark.parametrize(
    "data, line",
    [
        (b"a\r\nb\r\n", 1),
        (b"a\nb\nc\r\nd\n", 3),
        (b"a\r\x00b\n", 1),
        (b"a\x00\r\n", 1),
        (b"a\n\tb\nc\r\n", 3),
    ],
)
def test_cr_is_reported_before_other_controls(data, line):
    result = validate_script(data)
    assert result is not None
    assert (result.rule, result.line) == ("cr", line)


@pytest.mark.parametrize(
    "data, line",
    [
        (b"a\n\tb\n", 2),
        (b"a\x00b\n", 1),
        (b"a\n\xc2\x85b\n", 2),
    ],
)
def test_disallowed_control_is_a_violation_on_its_line(data, line):
    result = validate_script(data)
    assert result is not None
    assert (result.rule, result.line) == ("control", line)


@pytest.mark.parametrize(
    "text",
    [
        "## T\na\nb\n",
        "## T\na\n\ufeffb\n",
        "## T\na\u00a0b\n",
        "## T\na\u3000b\n",
        "## T\na\u200bb\n",
    ],
)
def test_non_cc_text_is_lexically_valid(text):
    assert validate_script(text.encode("utf-8")) is None


def test_cr_wins_over_a_control_on_a_later_line():
    result = validate_script(b"a\r\n\tb\n")
    assert result is not None
    assert (result.rule, result.line) == ("cr", 1)


@pytest.mark.parametrize(
    "data, rule, line",
    [
        (b"# Title\n\nsome text\n", "no-marker", None),
        (b"## \nbody\n", "blank-title", 1),
        (b"## A\n   \n", "blank-body", 1),
        (b"## A\n\xc2\xa0\xc2\xa0\n", "blank-body", 1),
        (b"## A\n\xe3\x80\x80\n", "blank-body", 1),
        (b"## A\ntext\n## B\n", "blank-body", 3),
        (b"## A\ntext\n## B", "blank-body", 3),
        ("## A\nx\u2028y\n## B\n".encode("utf-8"), "blank-body", 3),
        ("## A\nx\u2029y\n## B\n".encode("utf-8"), "blank-body", 3),
    ],
    ids=[
        "preamble-only",
        "blank-title",
        "whitespace-body",
        "nbsp-body",
        "ideographic-space-body",
        "final-marker-lf-eof",
        "final-marker-eof",
        "u2028-keeps-line-count",
        "u2029-keeps-line-count",
    ],
)
def test_scene_violation_is_reported(data, rule, line):
    result = validate_script(data)
    assert result is not None
    assert (result.rule, result.line) == (rule, line)


@pytest.mark.parametrize(
    "data",
    [
        b"## A\nfirst\n## B\nsecond\n",
        b"## A\nOne [pause] two.\n## B\nwhisper this\n## C\nsay this slowly\n",
        b"## A\n### not a marker\n  ## indented\ntext\n",
    ],
    ids=["two-scenes", "direction-like-text", "non-markers-in-body"],
)
def test_valid_scene_scripts_return_none(data):
    assert validate_script(data) is None


@pytest.mark.parametrize(
    "data, rule, line",
    [
        (b"\xef\xbb\xbfno marker here\n", "bom", 1),
        (b"## A\n\n\xff\n", "invalid-utf8", 3),
        (b"## A\r\n\n", "cr", 1),
        (b"## \n\tbody\n", "control", 2),
        (b"## A\n\tx\nb\r\n", "cr", 3),
    ],
    ids=["bom", "invalid-utf8", "cr", "control", "cr-before-earlier-tab"],
)
def test_lexical_violation_wins_over_scene_violation(data, rule, line):
    result = validate_script(data)
    assert result is not None
    assert (result.rule, result.line) == (rule, line)
