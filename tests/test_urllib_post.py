"""Offline tests for the urllib transport.

The real network call is covered only by WS10 live acceptance; here the error
mapping and the request wiring run through private helpers with a stub opener.
"""

import http.client
import io
import ssl
import urllib.error

import pytest

from scenevoice.synth.provider import ProviderError
from scenevoice.synth.urllib_post import _map_error, _post_with


def _http_error(code, body=b"", read_raises=False):
    class Body(io.BytesIO):
        def read(self, size=-1):
            if read_raises:
                raise OSError("body gone")
            return super().read(size)

    return urllib.error.HTTPError("https://example.test/x", code, "msg", {}, Body(body))


def test_http_error_message_has_code_and_body():
    error = _map_error(_http_error(403, b'{"error": "denied"}'))
    assert isinstance(error, ProviderError)
    assert str(error) == 'HTTP 403 {"error": "denied"}'


def test_http_error_body_is_capped_at_500_characters():
    error = _map_error(_http_error(500, b"a" * 5000))
    assert str(error) == "HTTP 500 " + "a" * 500


def test_http_error_reads_at_most_about_500_bytes():
    reads = []

    class Body(io.BytesIO):
        def read(self, size=-1):
            reads.append(size)
            return super().read(size)

    error = urllib.error.HTTPError("https://example.test/x", 500, "m", {}, Body(b"b" * 5000))
    _map_error(error)
    assert reads and 0 < reads[0] <= 600


def test_http_error_undecodable_body_does_not_raise():
    error = _map_error(_http_error(502, b"\xff\xfe bad"))
    assert isinstance(error, ProviderError)
    assert str(error).startswith("HTTP 502 ")
    assert "bad" in str(error)


def test_http_error_body_read_failure_gives_code_only():
    error = _map_error(_http_error(429, b"ignored", read_raises=True))
    assert str(error) == "HTTP 429"


def test_http_error_empty_body_gives_code_only():
    assert str(_map_error(_http_error(404, b""))) == "HTTP 404"


@pytest.mark.parametrize(
    ("exc", "name"),
    [
        (urllib.error.URLError("refused"), "URLError"),
        (TimeoutError("slow"), "TimeoutError"),
        (ConnectionResetError("reset"), "ConnectionResetError"),
        (http.client.IncompleteRead(b"ab"), "IncompleteRead"),
        (ValueError("Invalid header value b'a\\nb'"), "ValueError"),
    ],
)
def test_other_failures_are_classified_one_line(exc, name):
    error = _map_error(exc)
    assert isinstance(error, ProviderError)
    assert str(error).startswith("Vertex request failed: " + name)
    assert "\n" not in str(error)


def test_classified_message_does_not_embed_raw_secret_text():
    error = _map_error(ValueError("secret-key-123"))
    assert "secret-key-123" not in str(error)


class _Response(io.BytesIO):
    pass


def test_post_with_sends_post_and_returns_bytes():
    seen = {}

    def opener(request, timeout):
        seen["method"] = request.get_method()
        seen["url"] = request.full_url
        seen["headers"] = dict(request.header_items())
        seen["data"] = request.data
        seen["timeout"] = timeout
        return _Response(b"raw-bytes")

    result = _post_with(
        "https://example.test/p", {"X-Key": "k", "Content-Type": "application/json"}, b"{}", 180, opener=opener
    )
    assert result == b"raw-bytes"
    assert seen["method"] == "POST"
    assert seen["url"] == "https://example.test/p"
    assert seen["headers"]["X-key"] == "k"
    assert seen["headers"]["Content-type"] == "application/json"
    assert seen["data"] == b"{}"
    assert seen["timeout"] == 180


def test_post_with_maps_opener_failures():
    def opener(request, timeout):
        raise _http_error(500, b"boom")

    with pytest.raises(ProviderError, match="^HTTP 500 boom$") as info:
        _post_with("https://example.test/p", {}, b"", 1, opener=opener)
    assert isinstance(info.value.__cause__, urllib.error.HTTPError)


def test_post_with_maps_read_failure():
    class Broken(io.BytesIO):
        def read(self, size=-1):
            raise http.client.IncompleteRead(b"x")

    def opener(request, timeout):
        return Broken()

    with pytest.raises(ProviderError, match="IncompleteRead"):
        _post_with("https://example.test/p", {}, b"", 1, opener=opener)


def test_post_with_does_not_catch_keyboard_interrupt():
    def opener(request, timeout):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        _post_with("https://example.test/p", {}, b"", 1, opener=opener)


def test_urlerror_reason_is_appended():
    reason = "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"
    error = _map_error(urllib.error.URLError(reason))
    assert str(error) == f"Vertex request failed: URLError: {reason}"


def test_urlerror_with_exception_reason_shows_its_text():
    reason = ssl.SSLCertVerificationError(1, "certificate verify failed: unable to get local issuer")
    error = _map_error(urllib.error.URLError(reason))
    assert str(error) == f"Vertex request failed: URLError: {reason}"
    assert "unable to get local issuer" in str(error)


def test_urlerror_reason_is_capped_at_200_characters():
    error = _map_error(urllib.error.URLError("r" * 500))
    assert str(error) == "Vertex request failed: URLError: " + "r" * 200


def test_urlerror_reason_newlines_are_collapsed():
    error = _map_error(urllib.error.URLError("a\r\n\nb\nc"))
    assert str(error) == "Vertex request failed: URLError: a b c"


@pytest.mark.parametrize(
    ("exc", "text"),
    [
        (TimeoutError("timed out"), "Vertex request failed: TimeoutError: timed out"),
        (ConnectionResetError("reset\nby peer"), "Vertex request failed: ConnectionResetError: reset by peer"),
    ],
)
def test_other_oserror_text_is_appended_on_one_line(exc, text):
    assert str(_map_error(exc)) == text


def test_oserror_text_is_capped_at_200_characters():
    error = _map_error(OSError("z" * 400))
    assert str(error) == "Vertex request failed: OSError: " + "z" * 200


def test_http_exception_stays_class_name_only():
    error = _map_error(http.client.HTTPException("secret-key-123"))
    assert str(error) == "Vertex request failed: HTTPException"
