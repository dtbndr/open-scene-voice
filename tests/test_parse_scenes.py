from pathlib import Path

import pytest

from scenevoice.validation.parse_scenes import parse_scenes
from scenevoice.validation.scene import Scene
from scenevoice.validation.violation import Violation

ROOT = Path(__file__).resolve().parent.parent


def _tuples(text):
    result = parse_scenes(text)
    assert isinstance(result, list)
    assert all(isinstance(s, Scene) for s in result)
    return [(s.ordinal, s.title, s.body, s.line) for s in result]


@pytest.mark.parametrize(
    "text, expected",
    [
        # single scene, verbatim title/body with trailing LF, line of marker
        ("## Arrival\nHello.\n", [(1, "Arrival", "Hello.\n", 1)]),
        # preamble ignored, line counts preamble lines
        (
            "# Video title\n\n[Pronunciations]\nAurelius = Oh-REE-lee-us\n\n## Arrival\nHello.\n",
            [(1, "Arrival", "Hello.\n", 6)],
        ),
        # title not trimmed
        ("## Arrival\nx\n", [(1, "Arrival", "x\n", 1)]),
        ("##   Arrival\nx\n", [(1, "  Arrival", "x\n", 1)]),
        # repeated titles
        (
            "## Same\na\n## Same\nb\n",
            [(1, "Same", "a\n", 1), (2, "Same", "b\n", 3)],
        ),
        # Scene N: not interpreted
        (
            "## Scene 1\na\n## Scene 4\nb\n## Scene 6\nc\n",
            [(1, "Scene 1", "a\n", 1), (2, "Scene 4", "b\n", 3), (3, "Scene 6", "c\n", 5)],
        ),
        (
            "## Scene 2:\na\n## Scene 2:\nb\n",
            [(1, "Scene 2:", "a\n", 1), (2, "Scene 2:", "b\n", 3)],
        ),
        # interior blank lines and trailing LFs kept exactly
        ("## A\none\n\n\ntwo\n\n", [(1, "A", "one\n\n\ntwo\n\n", 1)]),
        # body ends immediately before next marker
        ("## A\none\n\n## B\ntwo\n", [(1, "A", "one\n\n", 1), (2, "B", "two\n", 4)]),
        # last scene without trailing LF
        ("## A\none", [(1, "A", "one", 1)]),
        # non-markers inside a body
        (
            "## A\n### h\n ## i\n##x\n##\n#\nend\n",
            [(1, "A", "### h\n ## i\n##x\n##\n#\nend\n", 1)],
        ),
        # marker right after a body line
        ("## A\nline\n## B\nx\n", [(1, "A", "line\n", 1), (2, "B", "x\n", 3)]),
        # literal direction-like text
        (
            "## A\n[pause]\nwhisper this\nsay this slowly\n",
            [(1, "A", "[pause]\nwhisper this\nsay this slowly\n", 1)],
        ),
        # ## mid-line is not a marker
        ("## A\nsay ## B now\n", [(1, "A", "say ## B now\n", 1)]),
        # U+2028 / U+2029 kept, do not split or advance line
        (
            "pre\u2028amble\n## T\u2028x\nb\u2029c\n## U\nd\n",
            [(1, "T\u2028x", "b\u2029c\n", 2), (2, "U", "d\n", 4)],
        ),
        # NBSP + letter body, U+3000 + letter title
        ("## A\n\u00a0x\n", [(1, "A", "\u00a0x\n", 1)]),
        ("## \u3000x\nb\n", [(1, "\u3000x", "b\n", 1)]),
    ],
)
def test_valid_scripts(text, expected):
    assert _tuples(text) == expected


def test_line_separators_do_not_shift_marker_lines():
    # splitlines() would split on U+2028 and move the second marker to line 5
    text = "## A\na\u2028b\u2029c\n## B\nd\n"
    assert _tuples(text) == [(1, "A", "a\u2028b\u2029c\n", 1), (2, "B", "d\n", 3)]


def test_sample_script():
    scenes = parse_scenes((ROOT / "sample/scripts/short.md").read_text(encoding="utf-8"))
    assert isinstance(scenes, list)
    assert [s.ordinal for s in scenes] == [1, 2, 3, 4, 5]


def test_sample_script_long():
    scenes = parse_scenes((ROOT / "sample/scripts/long.md").read_text(encoding="utf-8"))
    assert isinstance(scenes, list)
    assert [s.ordinal for s in scenes] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert scenes[4].title == "The Great Cannon"


def _violation(text):
    result = parse_scenes(text)
    assert isinstance(result, Violation)
    assert result.message
    return result.rule, result.line


@pytest.mark.parametrize(
    "text",
    [
        "",
        "# Video title\n\nSome preamble\n",
        "[Pronunciations]\nAurelius = Oh-REE-lee-us\n",
        "# Title\n",
        "### h\nx\n",
        " ## indented\nx\n",
        "##x\nbody\n",
        "##\nbody\n",
        "##\u200b\nbody\n",
    ],
)
def test_no_marker(text):
    assert _violation(text) == ("no-marker", None)


@pytest.mark.parametrize(
    "text, line",
    [
        ("## \nbody\n", 1),
        ("## \n", 1),
        ("## ", 1),  # ends in marker with nothing after: blank-title, not blank-body
        ("pre\n\n##    \nbody\n", 3),
        ("## \u00a0\nbody\n", 1),
        ("## \u3000\nbody\n", 1),
        ("## \u2028\nbody\n", 1),
        ("## \u2029\nbody\n", 1),
        ("## A\nx\n## \n\n", 3),  # both blank: title wins
        ("## \n## B\nx\n", 1),  # both blank: title wins
    ],
)
def test_blank_title(text, line):
    assert _violation(text) == ("blank-title", line)


@pytest.mark.parametrize(
    "text, line",
    [
        ("## A\n## B\nx\n", 1),
        ("## A\n   \n", 1),
        ("## A\n \n\n\u00a0\u3000\u2028\u2029\n", 1),
        ("## A\nx\n## B\n", 3),
        ("## A\nx\n## B", 3),
        ("# pre\n## A\n", 2),
        ("## A\nx\n## B\n\n\n   \n## C\ny\n", 3),
    ],
)
def test_blank_body(text, line):
    assert _violation(text) == ("blank-body", line)


def test_violation_reports_later_scene_marker_line_not_body_end():
    assert _violation("## A\nx\ny\nz\n## B\n \n \n \n") == ("blank-body", 5)


def test_first_violation_in_source_order_wins():
    assert _violation("## A\n## B\nx\n## \ny\n") == ("blank-body", 1)
    assert _violation("## A\nx\n## \ny\n## C\n") == ("blank-title", 3)


def test_valid_scene_does_not_mask_later_invalid_scene():
    assert _violation("## A\nx\n## B\n \n") == ("blank-body", 3)


@pytest.mark.parametrize("body", ["\u200b", "\ufeff", "\u200b\ufeff"])
def test_zwsp_and_feff_are_not_white_space(body):
    assert _tuples(f"## A\n{body}\n") == [(1, "A", f"{body}\n", 1)]
