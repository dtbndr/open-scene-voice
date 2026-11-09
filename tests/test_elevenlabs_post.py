"""Transport tests for the ElevenLabs label and status check (no network)."""

import io
import sys
import urllib.error

import pytest

import scenevoice.synth.elevenlabs_post  # noqa: F401  (ensures the module is loaded)
from scenevoice.synth.provider import ProviderError
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
