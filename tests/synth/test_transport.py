"""Transport tests for the ElevenLabs label and status check (no network)."""

import io
import sys
import urllib.error

import pytest

import scenevoice.synth.elevenlabs_post  # noqa: F401  (ensures the module is loaded)
from scenevoice.synth.provider import ProviderError
from scenevoice.synth.redact_secret import redact_secret
from scenevoice.synth.secret_header_values import secret_header_values
from scenevoice.synth.urllib_post import _map_error, _post_with


class _Response(io.BytesIO):
    def __init__(self, data, status):
        super().__init__(data)
        self.status = status


def _http_error(code, body=b""):
    return urllib.error.HTTPError(
        "https://example.test/x", code, "msg", {}, io.BytesIO(body)
    )


def _opener_returning(data, status):
    def opener(request, timeout):
        return _Response(data, status)

    return opener


def test_post_with_returns_body_for_expected_status():
    result = _post_with(
        "https://example.test/p",
        {},
        b"{}",
        1,
        label="ElevenLabs",
        expect_status=200,
        opener=_opener_returning(b"ok", 200),
    )
    assert result == b"ok"


def test_post_with_rejects_other_success_status():
    with pytest.raises(ProviderError) as info:
        _post_with(
            "https://example.test/p",
            {},
            b"{}",
            1,
            label="ElevenLabs",
            expect_status=200,
            opener=_opener_returning(b"x", 201),
        )
    assert str(info.value) == "HTTP 201"


def test_post_with_maps_url_error_with_label():
    def opener(request, timeout):
        raise urllib.error.URLError("no route")

    with pytest.raises(ProviderError) as info:
        _post_with(
            "https://example.test/p",
            {},
            b"",
            1,
            label="ElevenLabs",
            expect_status=200,
            opener=opener,
        )
    assert str(info.value) == "ElevenLabs request failed: URLError: no route"


def test_map_error_http_status_is_in_the_message():
    error = _map_error(_http_error(401, b'{"detail": "x"}'), label="ElevenLabs")
    assert str(error) == 'HTTP 401 {"detail": "x"}'


def test_elevenlabs_post_calls_post_with_label_and_status():
    module = sys.modules["scenevoice.synth.elevenlabs_post"]
    calls = []

    def recorder(*args, **kwargs):
        calls.append((args, kwargs))
        return b"raw"

    original = module._post_with
    module._post_with = recorder
    try:
        result = module.elevenlabs_post(
            "https://example.test/p", {"k": "v"}, b"{}", 180
        )
    finally:
        module._post_with = original
    assert calls, "positive control: the recorder was reached"
    assert result == b"raw"
    assert calls[0][0] == ("https://example.test/p", {"k": "v"}, b"{}", 180)
    assert calls[0][1] == {"label": "ElevenLabs", "expect_status": 200}


@pytest.mark.parametrize("name", ["xi-api-key", "x-GOOG-api-KEY"])
def test_secret_headers_yield_their_value_in_any_case(name):
    assert secret_header_values({name: "k", "Content-Type": "application/json"}) == ["k"]


@pytest.mark.parametrize("name", ["Authorization"])
def test_authorization_yields_full_value_and_bare_bearer_token(name):
    assert secret_header_values({name: "Bearer tok"}) == ["Bearer tok", "tok"]


SECRET = "sk-distinct-123\n"


def test_raw_and_stripped_forms_are_replaced():
    message = "bad key 'sk-distinct-123\n' and sk-distinct-123 again sk-distinct-123"
    out = redact_secret(message, SECRET)
    assert "sk-distinct-123" not in out
    assert out.count("[redacted]") == 3


def test_message_without_secret_is_unchanged():
    assert redact_secret("scene 1: nothing here", SECRET) == "scene 1: nothing here"


def test_raw_form_with_padding_is_replaced_whole():
    out = redact_secret("x  key \n y", "  key \n")
    assert out == "x[redacted] y"


def test_empty_whitespace_and_none_secret_leave_message_unchanged():
    message = "keep  \n this"
    for secret in ("", "  \n\t", None):
        assert redact_secret(message, secret) == message
