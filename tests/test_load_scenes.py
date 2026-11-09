from pathlib import Path

import pytest

from scenevoice.validation import Violation, load_scenes

ROOT = Path(__file__).resolve().parent.parent


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
        (b"## A\n   \n", "blank-body", 1),
        (b"## A\ntext\n## B\n", "blank-body", 3),
    ],
    ids=["bom", "invalid-utf8", "cr", "control", "no-marker", "blank-title", "blank-body", "blank-final-body"],
)
def test_rejection_returns_the_violation(data, rule, line):
    result = load_scenes(data)
    assert isinstance(result, Violation)
    assert (result.rule, result.line) == (rule, line)


def test_cr_is_checked_before_controls():
    result = load_scenes(b"a\r\n\tb\n")
    assert isinstance(result, Violation)
    assert (result.rule, result.line) == ("cr", 1)
