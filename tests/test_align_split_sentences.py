import pytest

from scenevoice.align import split_sentences

CASES = [
    ('He said, "Stop." Then he left.', ['He said, "Stop."', "Then he left."]),
    ("He said, “Stop.” Then he left.", ["He said, “Stop.”", "Then he left."]),
    ("Welcome back\n\nToday we start. It is easy.", ["Welcome back", "Today we start.", "It is easy."]),
    ("First line.\r\nSecond line.", ["First line.", "Second line."]),
    ("Heading without stop\r\n\r\nNext part.", ["Heading without stop", "Next part."]),
    ("This sentence is long\nand wraps here. Next one!", ["This sentence is long and wraps here.", "Next one!"]),
    ("Two  spaces\tand a nbsp here.  Done.", ["Two spaces and a nbsp here.", "Done."]),
    ("  \nHello there. \n", ["Hello there."]),
    ("It costs 3.5 dollars. Fine.", ["It costs 3.5 dollars.", "Fine."]),
    ("Wait... what? Yes.", ["Wait...", "what?", "Yes."]),
    ("Dr. Smith arrived. He sat down.", ["Dr.", "Smith arrived.", "He sat down."]),
    ("Hello. ... Next.", ["Hello.", "...", "Next."]),
    ("Hello.\n\n...\n\nNext.", ["Hello.", "...", "Next."]),
    ("One.Two", ["One.Two"]),
    ("Really?! Yes.", ["Really?!", "Yes."]),
    ("(Stop.) Go.", ["(Stop.)", "Go."]),
    ("[Stop.] Go.", ["[Stop.]", "Go."]),
    ("'Stop.' Go.", ["'Stop.'", "Go."]),
    ("‘Stop.’ Go.", ["‘Stop.’", "Go."]),
    ("No terminator", ["No terminator"]),
    ("", []),
    (" \n ", []),
]


@pytest.mark.parametrize(("body", "expected"), CASES)
def test_split_sentences(body: str, expected: list[str]) -> None:
    assert split_sentences(body) == expected


@pytest.mark.parametrize("ch", ["\r", "\u0085", " ", " "])
def test_lone_cr_and_unicode_line_breaks_are_not_blank_lines(ch: str) -> None:
    assert split_sentences(f"a{ch}{ch}b") == ["a b"]


def test_cr_and_lf_pair_across_blank_line_counts_lf_only() -> None:
    assert split_sentences("a\r\rb") == ["a b"]
    assert split_sentences("a\n\rb") == ["a b"]
    assert split_sentences("a\n\r\nb") == ["a", "b"]


@pytest.mark.parametrize("ch", ["\u001c", "\u001d", "\u001e", "\u001f"])
def test_separator_controls_are_not_whitespace(ch: str) -> None:
    assert split_sentences(f"a.{ch}b") == [f"a.{ch}b"]
    assert split_sentences(f"a{ch}{ch} b") == [f"a{ch}{ch} b"]
    assert split_sentences(f"{ch}") == [ch]


def test_terminator_followed_by_unicode_whitespace_splits() -> None:
    assert split_sentences("A.　B.") == ["A.", "B."]
