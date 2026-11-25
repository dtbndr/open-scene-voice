import base64
import json
import math

import pytest

from scenevoice.align import (
    seconds_to_ms,
    sentence_offsets,
    split_sentences,
    word_tokens,
)
from scenevoice.align.build_transcription_request import build_transcription_request
from scenevoice.align.white_space import WHITE_SPACE_RUN

CASES = [
    ('He said, "Stop." Then he left.', ['He said, "Stop."', "Then he left."]),
    ("Welcome back\n\nToday we start. It is easy.", ["Welcome back", "Today we start.", "It is easy."]),
    ("First line.\r\nSecond line.", ["First line.", "Second line."]),
    ("This sentence is long\nand wraps here. Next one!", ["This sentence is long and wraps here.", "Next one!"]),
    ("  \nHello there. \n", ["Hello there."]),
    ("It costs 3.5 dollars. Fine.", ["It costs 3.5 dollars.", "Fine."]),
    ("Wait... what? Yes.", ["Wait...", "what?", "Yes."]),
    ("Dr. Smith arrived. He sat down.", ["Dr.", "Smith arrived.", "He sat down."]),
    ("Hello. ... Next.", ["Hello.", "...", "Next."]),
    ("One.Two", ["One.Two"]),
    ("Really?! Yes.", ["Really?!", "Yes."]),
    ("(Stop.) Go.", ["(Stop.)", "Go."]),
    ("No terminator", ["No terminator"]),
    ("", []),
]


@pytest.mark.parametrize(("body", "expected"), CASES)
def test_split_sentences(body: str, expected: list[str]) -> None:
    assert split_sentences(body) == expected


@pytest.mark.parametrize("ch", ["\r", "\u0085"])
def test_lone_cr_and_unicode_line_breaks_are_not_blank_lines(ch: str) -> None:
    assert split_sentences(f"a{ch}{ch}b") == ["a b"]


def test_cr_and_lf_pair_across_blank_line_counts_lf_only() -> None:
    assert split_sentences("a\r\rb") == ["a b"]
    assert split_sentences("a\n\rb") == ["a b"]
    assert split_sentences("a\n\r\nb") == ["a", "b"]


@pytest.mark.parametrize("ch", ["\u001c"])
def test_separator_controls_are_not_whitespace(ch: str) -> None:
    assert split_sentences(f"a.{ch}b") == [f"a.{ch}b"]
    assert split_sentences(f"a{ch}{ch} b") == [f"a{ch}{ch} b"]
    assert split_sentences(f"{ch}") == [ch]


def test_terminator_followed_by_unicode_whitespace_splits() -> None:
    assert split_sentences("A.　B.") == ["A.", "B."]


ORACLES = [
    ("Hi there. Go on.", [0, 10]),
    ("First line.\r\nSecond line.", [0, 13]),
    ("  \nHello there. \n", [3]),
    ("Hello. ... Next.", [0, 7, 11]),
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


@pytest.mark.parametrize(
    ("text", "tokens"),
    [
        ("word—word", ["wordword"]),
        ("Hello,", ["hello"]),
        ("don't", ["don't"]),
        ("...", []),
        ("Hello world", ["hello", "world"]),
        ("two words", ["two", "words"]),
    ],
)
def test_token_table(text: str, tokens: list[str]) -> None:
    assert word_tokens(text) == tokens


def test_curly_apostrophe_is_dropped_not_folded() -> None:
    assert word_tokens("don’t") == ["dont"]
    assert word_tokens("don't") == ["don't"]
    assert word_tokens("don’t") != word_tokens("don't")


def test_accented_letters_are_dropped() -> None:
    assert word_tokens("café") == ["caf"]


@pytest.mark.parametrize("ch", ["\u001c"])
def test_separator_controls_do_not_split(ch: str) -> None:
    assert word_tokens(f"a{ch}b") == ["ab"]


@pytest.mark.parametrize(
    ("start", "expected"),
    [
        (0.23999999865889549, 240),
        (1.2346, 1235),
        (0, 0),
        (2, 2000),
    ],
)
def test_milliseconds(start: float, expected: int) -> None:
    result = seconds_to_ms(start)
    assert result == expected
    assert type(result) is int


@pytest.mark.parametrize(
    "start", [math.nan, 1e308]
)
def test_overflow_and_non_finite_return_none(start: float) -> None:
    assert seconds_to_ms(start) is None


WAV = b"RIFF\x00\x01\xff\xfe-binary-bytes"


def _body() -> dict:
    return json.loads(build_transcription_request(WAV))


def test_exact_keys() -> None:
    assert set(_body()) == {
        "model",
        "input_audio",
        "language",
        "response_format",
        "timestamp_granularities",
    }


def test_constant_fields() -> None:
    body = _body()
    assert body["model"] == "openai/whisper-large-v3-turbo"
    assert body["language"] == "en"
    assert body["response_format"] == "verbose_json"
    assert body["timestamp_granularities"] == ["word", "segment"]


def test_input_audio_shape_and_round_trip() -> None:
    audio = _body()["input_audio"]
    assert set(audio) == {"data", "format"}
    assert audio["format"] == "wav"
    assert not audio["data"].startswith("data:")
    assert base64.b64decode(audio["data"], validate=True) == WAV


def test_returns_bytes() -> None:
    assert isinstance(build_transcription_request(WAV), bytes)
