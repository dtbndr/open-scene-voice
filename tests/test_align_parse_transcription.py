import json
from pathlib import Path

import pytest

from scenevoice.align import TranscriptionError, parse_transcription
from scenevoice.synth import ProviderError

FIXTURES = Path(__file__).parent / "fixtures" / "openrouter"


def _body(words: list[object]) -> bytes:
    return json.dumps({"words": words}).encode()


def _w(word: str, start: object) -> dict[str, object]:
    return {"word": word, "start": start, "end": 1.0}


def test_real_fixture_accepted() -> None:
    result = parse_transcription((FIXTURES / "whisper_verbose_json.json").read_bytes())
    assert not isinstance(result, str)
    assert len(result) == 36
    assert result[0][1] == pytest.approx(0.24, abs=1e-6)
    assert all(token == token.lower() and " " not in token for token, _ in result)


@pytest.mark.parametrize(
    ("body", "fragment"),
    [
        (b"not json", "not JSON"),
        (b"\xff\xfe\x00", "not JSON"),
        (b"[1]", "object"),
        (b'"x"', "object"),
        (b"{}", "words"),
        (b'{"words": []}', "no words array"),
        (b'{"words": "abc"}', "words"),
        (b'{"words": {"a": 1}}', "words"),
        (_body([1]), "not an object"),
        (_body([_w("a", 0), "x"]), "not an object"),
        (_body([{"word": 5, "start": 0}]), "not a string"),
        (_body([{"start": 0}]), "not a string"),
        (_body([{"word": "a"}]), "start"),
        (_body([_w("a", True)]), "start"),
        (_body([_w("a", False)]), "start"),
        (_body([_w("a", "1.0")]), "start"),
        (_body([_w("a", None)]), "start"),
        (_body([_w("a", -0.5)]), "negative"),
        (_body([_w("a", -1)]), "negative"),
        (b'{"words": [{"word": "a", "start": NaN}]}', "finite"),
        (b'{"words": [{"word": "a", "start": Infinity}]}', "finite"),
        (b'{"words": [{"word": "a", "start": -Infinity}]}', "negative"),
        (b'{"words": [{"word": "a", "start": 1e999}]}', "finite"),
        (b'{"words": [{"word": "a", "start": ' + b"9" * 400 + b"}]}", "finite"),
        (_body([_w("a", 2.0), _w("b", 1.0)]), "decrease"),
        (_body([_w("a", 2.0), _w("...", 3.0), _w("b", 2.5)]), "decrease"),
        (_body([_w(" ,", 0.0), _w("...", 1.0)]), "normalisation"),
        (_body([_w("", 0.0)]), "normalisation"),
    ],
)
def test_malformed(body: bytes, fragment: str) -> None:
    result = parse_transcription(body)
    assert isinstance(result, str)
    assert fragment in result


def test_negative_zero_accepted_as_zero() -> None:
    result = parse_transcription(b'{"words": [{"word": "a", "start": -0.0}]}')
    assert result == [("a", 0.0)]


def test_integer_start_accepted() -> None:
    assert parse_transcription(_body([_w(" Hi", 2)])) == [("hi", 2.0)]


def test_equal_consecutive_starts_allowed() -> None:
    result = parse_transcription(_body([_w("a", 1.0), _w("b", 1.0)]))
    assert result == [("a", 1.0), ("b", 1.0)]


def test_internal_whitespace_shares_start() -> None:
    result = parse_transcription(_body([_w(" one two", 1.5), _w("three", 2.0)]))
    assert result == [("one", 1.5), ("two", 1.5), ("three", 2.0)]


def test_punctuation_entry_skipped_but_ordering_checked() -> None:
    assert parse_transcription(_body([_w("a", 1.0), _w(".", 1.5), _w("b", 2.0)])) == [
        ("a", 1.0),
        ("b", 2.0),
    ]


def test_extra_fields_ignored() -> None:
    body = json.dumps(
        {"words": [_w("A.", 0.5)], "duration": "x", "segments": [{"id": 0}, {"id": 0}]}
    ).encode()
    assert parse_transcription(body) == [("a", 0.5)]


@pytest.mark.parametrize("name", ["error_401.json", "error_400.json"])
def test_error_fixtures_shape(name: str) -> None:
    document = json.loads((FIXTURES / name).read_bytes())
    assert set(document) == {"error"}
    assert set(document["error"]) == {"message", "code"}
    assert isinstance(document["error"]["message"], str)
    assert document["error"]["code"] == int(name[6:9])
    assert isinstance(parse_transcription((FIXTURES / name).read_bytes()), str)


def test_transcription_error_shape() -> None:
    error = TranscriptionError(401, "User not found.")
    assert isinstance(error, ProviderError)
    assert error.status == 401
    assert str(error) == "User not found."
    assert TranscriptionError(None, "timed out").status is None
