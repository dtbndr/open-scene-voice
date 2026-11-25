"""Offline tests for the urllib transport.

The real network call is covered only by WS10 live acceptance; here the error
mapping and the request wiring run through private helpers with a stub opener.
"""

import http.client
import io
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


def test_http_error_body_read_failure_gives_code_only():
    error = _map_error(_http_error(429, b"ignored", read_raises=True))
    assert str(error) == "HTTP 429"


@pytest.mark.parametrize(
    ("exc", "name"),
    [
        (urllib.error.URLError("refused"), "URLError"),
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


def test_urlerror_reason_is_appended():
    reason = "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"
    error = _map_error(urllib.error.URLError(reason))
    assert str(error) == f"Vertex request failed: URLError: {reason}"


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


def test_http_exception_stays_class_name_only():
    error = _map_error(http.client.HTTPException("secret-key-123"))
    assert str(error) == "Vertex request failed: HTTPException"


_KEY = "CANARY-key-0123456789"
_HEADERS = {"xi-api-key": _KEY, "Content-Type": "application/json"}


def _post_failing_with(body, headers):
    def opener(request, timeout):
        raise _http_error(403, body)

    with pytest.raises(ProviderError) as info:
        _post_with("https://example.test/p", headers, b"{}", 5, opener=opener)
    return str(info.value)


@pytest.mark.parametrize("lead", [499])
def test_key_straddling_the_excerpt_cut_leaves_no_prefix(lead):
    body = ("x" * lead + _KEY + "y" * 600).encode()
    text = _post_failing_with(body, _HEADERS)
    assert text == "HTTP 403 " + ("x" * lead + "[redacted]" + "y" * 600)[:500]
    assert _KEY[:6] not in text


def test_key_after_four_byte_characters_is_read_whole_and_redacted():
    body = ("\U0001f600" * 499 + _KEY + "tail").encode()
    text = _post_failing_with(body, _HEADERS)
    assert text == "HTTP 403 " + ("\U0001f600" * 499 + "[redacted]tail")[:500]
    assert _KEY[:6] not in text


def test_body_repeating_the_key_many_times_leaves_no_fragment():
    key = "CANARY-" + "k" * 66
    text = _post_failing_with((key * 31).encode(), {"xi-api-key": key})
    assert text == "HTTP 403 " + "[redacted]" * 31


def test_post_with_redacts_the_key_from_the_headers_it_was_given():
    text = _post_failing_with(f'{{"error": "bad {_KEY} tail"}}'.encode(), _HEADERS)
    assert text == 'HTTP 403 {"error": "bad [redacted] tail"}'


@pytest.mark.parametrize("code", [429])
def test_http_error_carries_its_status_and_is_not_a_transport_failure(code):
    error = _map_error(_http_error(code, b"nope"))
    assert str(error) == f"HTTP {code} nope"
    assert error.status == code
    assert error.transport is False


@pytest.mark.parametrize(
    "exc",
    [
        urllib.error.URLError("refused"),
        ConnectionResetError("reset"),
        http.client.RemoteDisconnected("closed"),
    ],
)
def test_transport_failures_have_no_status_and_are_transport(exc):
    error = _map_error(exc)
    assert error.status is None
    assert error.transport is True


@pytest.mark.parametrize("exc", [ValueError("bad")])
def test_value_errors_have_no_status_and_are_not_transport(exc):
    error = _map_error(exc)
    assert error.status is None
    assert error.transport is False


def test_expect_status_mismatch_carries_the_seen_status():
    class Response(_Response):
        status = 201

    def opener(request, timeout):
        return Response(b"")

    with pytest.raises(ProviderError, match="^HTTP 201$") as info:
        _post_with("https://example.test/p", {}, b"", 1, expect_status=200, opener=opener)
    assert info.value.status == 201
    assert info.value.transport is False
