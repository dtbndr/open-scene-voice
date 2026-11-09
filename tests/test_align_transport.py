import http.client
import io
import json
import urllib.error
from pathlib import Path
from typing import Any

import pytest

from scenevoice.align.make_openrouter_transcriber import make_openrouter_transcriber
from scenevoice.align.openrouter_transcriber import openrouter_transcriber
from scenevoice.align.transcription_error import TranscriptionError

FIXTURES = Path(__file__).parent / "fixtures" / "openrouter"
URL = "https://openrouter.ai/api/v1/audio/transcriptions"
WAV = b"RIFFwav"
KEY = "sk-or-secret"


class _Response:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class _Opener:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.request: Any = None
        self.timeout: Any = None

    def __call__(self, request: Any, timeout: Any = None) -> Any:
        self.request = request
        self.timeout = timeout
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def _call(opener: _Opener, key: str = KEY) -> bytes:
    return openrouter_transcriber(WAV, key, opener=opener)


def _http_error(code: int, body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(URL, code, "x", http.client.HTTPMessage(), io.BytesIO(body))


def test_success_returns_body_and_request_shape() -> None:
    opener = _Opener(_Response(200, b'{"ok":1}'))
    assert _call(opener) == b'{"ok":1}'
    req = opener.request
    assert req.full_url == URL
    assert req.get_method() == "POST"
    assert req.get_header("Authorization") == f"Bearer {KEY}"
    assert req.get_header("Content-type") == "application/json"
    assert json.loads(req.data)["input_audio"]["format"] == "wav"
    assert isinstance(opener.timeout, (int, float))


@pytest.mark.parametrize("name", ["error_401", "error_400"])
def test_http_error_fixtures(name: str) -> None:
    raw = (FIXTURES / f"{name}.json").read_bytes()
    code = json.loads(raw)["error"]["code"]
    with pytest.raises(TranscriptionError) as info:
        _call(_Opener(_http_error(code, raw)))
    assert info.value.status == code
    assert json.loads(raw)["error"]["message"] in info.value.text


def test_http_error_empty_body_keeps_status() -> None:
    with pytest.raises(TranscriptionError) as info:
        _call(_Opener(_http_error(500, b"")))
    assert info.value.status == 500


def test_http_error_body_capped() -> None:
    with pytest.raises(TranscriptionError) as info:
        _call(_Opener(_http_error(502, b"x" * 5000)))
    assert info.value.status == 502
    assert len(info.value.text) <= 500


@pytest.mark.parametrize("status", [201, 202, 204])
def test_non_200_returned_normally_raises(status: int) -> None:
    with pytest.raises(TranscriptionError) as info:
        _call(_Opener(_Response(status, b"")))
    assert info.value.status == status


@pytest.mark.parametrize(
    "exc",
    [
        urllib.error.URLError("no route"),
        TimeoutError("timed out"),
        ConnectionResetError("reset"),
    ],
)
def test_transport_errors_have_no_status(exc: BaseException) -> None:
    with pytest.raises(TranscriptionError) as info:
        _call(_Opener(exc))
    assert info.value.status is None
    assert type(exc).__name__ in info.value.text


@pytest.mark.parametrize("exc_type", [ValueError, http.client.HTTPException])
def test_value_and_http_exception_class_name_only(exc_type: type[Exception]) -> None:
    with pytest.raises(TranscriptionError) as info:
        _call(_Opener(exc_type(f"bad header {KEY}")))
    assert info.value.status is None
    assert KEY not in info.value.text
    assert exc_type.__name__ in info.value.text


def test_factory_strips_key_and_returns_callable() -> None:
    opener = _Opener(_Response(200, b"{}"))
    transcriber = make_openrouter_transcriber(f"  {KEY}\n", opener=opener)
    assert transcriber(WAV) == b"{}"
    assert opener.request.get_header("Authorization") == f"Bearer {KEY}"
