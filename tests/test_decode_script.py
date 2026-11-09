import pytest

from scenevoice.validation.decode_script import decode_script
from scenevoice.validation.violation import Violation


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
    assert result.message


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
    assert result.message
