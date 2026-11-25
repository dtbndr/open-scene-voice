"""Prove every tagged example in docs/script-format.md against the real parser.

Fence-tag convention (info string of a fenced block in the guide):

- ``script-valid scenes=N``: the block text plus one final LF parses into
  exactly N scenes with ordinals 1..N.
- ``script-invalid rule=R line=L``: the same text is rejected with
  ``Violation.rule == R`` and ``Violation.line == L``. Omit ``line=`` when the
  violation carries no line (for example ``no-marker``).

Every fenced block must carry exactly one of those two tags or a tag listed in
``NON_SCRIPT_TAGS``. Any other info string (untagged, ``scirpt-valid``,
``Script-valid``) fails the test, so a mistyped tag cannot skip a check.
"""

import re
from typing import NamedTuple

import pytest
from paths_helper import REPO_ROOT as ROOT

from scenevoice.cli.main import main
from scenevoice.validation import Violation, load_scenes

GUIDE = ROOT / "docs" / "script-format.md"
FENCE = re.compile(r"^```([^\n]*)\n(.*?)\n```[ \t]*$", re.DOTALL | re.MULTILINE)


NON_SCRIPT_TAGS = frozenset({"text"})  # explicitly allowed non-script fences
SCRIPT_TAGS = frozenset({"script-valid", "script-invalid"})


class Example(NamedTuple):
    tag: str
    attrs: dict[str, str]
    text: str


def _infos(source: str) -> list[str]:
    return [info.strip() for info, _ in FENCE.findall(source)]


def _bad_info_strings(source: str) -> list[str]:
    bad = []
    for info in _infos(source):
        words = info.split()
        if not words or words[0] not in SCRIPT_TAGS | NON_SCRIPT_TAGS:
            bad.append(info)
    return bad


def _extract() -> list[Example]:
    source = GUIDE.read_text(encoding="utf-8") if GUIDE.exists() else ""
    found = []
    for info, text in FENCE.findall(source):
        words = info.split()
        if not words or not words[0].startswith("script"):
            continue
        attrs = dict(w.split("=", 1) for w in words[1:] if "=" in w)
        found.append(Example(words[0], attrs, text))
    return found


def _of(tag: str) -> list[Example]:
    return [e for e in _extract() if e.tag == tag]


def _data(example: Example) -> bytes:
    return (example.text + "\n").encode("utf-8")


def _cli_exit(example: Example, tmp_path, capsysbinary) -> int:
    path = tmp_path / "script.md"
    path.write_bytes(_data(example))
    code = main(["plan", str(path)])
    capsysbinary.readouterr()
    return code


def test_guide_has_valid_and_invalid_examples():
    assert GUIDE.exists()
    assert _of("script-valid")
    assert _of("script-invalid")


def test_every_fence_has_a_known_tag():
    assert _bad_info_strings(GUIDE.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    "info", ["", "script-valdi"]
)
def test_unknown_or_mistyped_fence_info_is_flagged(info):
    source = f"```{info}\n## A\nb\n```\n"
    assert _bad_info_strings(source) == [info]


def test_known_fence_tags_are_not_flagged():
    source = "```script-valid scenes=1\n## A\nb\n```\n```text\nx\n```\n"
    assert _bad_info_strings(source) == []


def test_guide_names_tabs_as_rejected_and_parser_agrees():
    result = load_scenes(b"## Opening\n\tHello.\n")
    assert isinstance(result, Violation)
    assert (result.rule, result.line) == ("control", 2)
    prose = GUIDE.read_text(encoding="utf-8")
    assert "tab" in prose.lower()
    assert any(
        e.tag == "script-invalid" and e.attrs.get("rule") == "control" and "\t" in e.text
        for e in _extract()
    )


@pytest.mark.parametrize("example", _of("script-valid"), ids=lambda e: e.text[:30])
def test_valid_example_parses_to_stated_scenes(example):
    scenes = load_scenes(_data(example))
    assert not isinstance(scenes, Violation)
    assert len(scenes) == int(example.attrs["scenes"])
    assert [s.ordinal for s in scenes] == list(range(1, len(scenes) + 1))
    assert all(s.title.strip() and s.body.strip() for s in scenes)


@pytest.mark.parametrize("example", _of("script-invalid"), ids=lambda e: e.text[:30])
def test_invalid_example_is_rejected_with_stated_rule(example):
    result = load_scenes(_data(example))
    assert isinstance(result, Violation)
    assert result.rule == example.attrs["rule"]
    expected = example.attrs.get("line")
    assert result.line == (int(expected) if expected is not None else None)


@pytest.mark.parametrize("example", _extract(), ids=lambda e: e.text[:30])
def test_cli_plan_agrees_with_tag(example, tmp_path, capsysbinary):
    expected = 0 if example.tag == "script-valid" else 1
    assert _cli_exit(example, tmp_path, capsysbinary) == expected


def test_guide_says_crlf_is_rejected_and_parser_agrees():
    result = load_scenes(b"## Opening\r\nHello.\r\n")
    assert isinstance(result, Violation) and result.rule == "cr"
    prose = GUIDE.read_text(encoding="utf-8")
    assert "CRLF" in prose
    assert "are fine" not in prose
