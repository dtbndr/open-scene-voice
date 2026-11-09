import pytest

from scenevoice.align import sentence_offsets, split_sentences
from scenevoice.align.white_space import WHITE_SPACE_RUN
from tests.test_align_split_sentences import CASES

ORACLES = [
    ("Hi there. Go on.", [0, 10]),
    ("Yes. Yes.", [0, 5]),
    ("\u001cHi. Go.", [0, 5]),
    ("First line.\r\nSecond line.", [0, 13]),
    ("Heading without stop\r\n\r\nNext part.", [0, 24]),
    ("  \nHello there. \n", [3]),
    ("This sentence is long\nand wraps here. Next one!", [0, 38]),
    ("Hello. ... Next.", [0, 7, 11]),
    ("Welcome back. Today we start.", [0, 14]),
    ("Keep it simple. See you next time.", [0, 16]),
]


@pytest.mark.parametrize(("body", "expected"), ORACLES)
def test_sentence_offsets_oracles(body: str, expected: list[int]) -> None:
    assert sentence_offsets(body) == expected


@pytest.mark.parametrize("body", [case[0] for case in CASES] + [case[0] for case in ORACLES])
def test_offsets_agree_with_split_sentences(body: str) -> None:
    offsets = sentence_offsets(body)
    sentences = split_sentences(body)
    assert len(offsets) == len(sentences)
    for offset, sentence in zip(offsets, sentences, strict=True):
        assert not WHITE_SPACE_RUN.fullmatch(body[offset])
        assert body[offset] == sentence[0]
