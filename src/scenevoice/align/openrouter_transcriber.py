import http.client
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from scenevoice.align.build_transcription_request import build_transcription_request
from scenevoice.align.match_constants import ALIGN_URL, REQUEST_TIMEOUT_SECONDS
from scenevoice.align.transcription_error import TranscriptionError
from scenevoice.synth.one_line import one_line

_EXCERPT_CHARS = 500
_DETAIL_CHARS = 200


def _detail(value: object) -> str:
    return one_line(str(value))[:_DETAIL_CHARS]


def _map_error(exc: Exception) -> TranscriptionError:
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body = exc.read(_EXCERPT_CHARS * 4).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return TranscriptionError(exc.code, one_line(body)[:_EXCERPT_CHARS])
    name = type(exc).__name__
    # ValueError and HTTPException text can carry header values (the key).
    if isinstance(exc, urllib.error.URLError):
        return TranscriptionError(None, f"{name}: {_detail(exc.reason)}")
    if isinstance(exc, OSError):
        return TranscriptionError(None, f"{name}: {_detail(exc)}")
    return TranscriptionError(None, name)


def openrouter_transcriber(
    wav: bytes,
    key: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> bytes:
    """POST one WAV to OpenRouter; return the body of an exact 200 response."""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    request = urllib.request.Request(
        ALIGN_URL, data=build_transcription_request(wav), headers=headers, method="POST"
    )
    try:
        with opener(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            status = response.status
            body: bytes = response.read()
    except (OSError, http.client.HTTPException, ValueError) as exc:
        raise _map_error(exc) from exc
    if status != 200:
        raise TranscriptionError(status, f"HTTP {status}")
    return body
