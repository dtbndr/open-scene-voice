import pytest

from scenevoice.synth import decode_json_document
from scenevoice.validation import Violation


@pytest.mark.parametrize(
    "data",
    [
        b'{"a": "\xff"}',
        b'\xef\xbb\xbf{"a": 1}',
        b'{"a": 1} x',
        b'{"a": 1, "a": 2}',
        b'{"a": NaN}',
        b'{"a": Infinity}',
        b"[" * 100000 + b"]" * 100000,
        b"",
        b" \n\t\r",
        b'{"a": ' + b"9" * 5000 + b"}",
        b'{"a": ',
    ],
    ids=[
        "bad-utf8", "bom", "trailing", "duplicate", "nan", "infinity",
        "deep", "empty", "whitespace", "huge-int", "truncated",
    ],
)
def test_rejects_with_violation(data: bytes) -> None:
    assert isinstance(decode_json_document(data), Violation)


def test_accepts_document_with_trailing_whitespace() -> None:
    assert decode_json_document(b' {"a": [1, 2.5, null]}\n') == {"a": [1, 2.5, None]}


def test_accepts_non_object_document() -> None:
    assert decode_json_document(b"[1]") == [1]
