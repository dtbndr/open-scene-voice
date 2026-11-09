"""Stdlib HTTP POST transport for the Vertex adapter.

Every failure becomes ProviderError. The transport never sees the API key as a
value to redact. The real network call is covered only by WS10 live acceptance;
tests exercise `_map_error` and `_post_with` with locally built errors and a
stub opener.
"""

import http.client
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from scenevoice.synth.one_line import one_line
from scenevoice.synth.provider import ProviderError

_EXCERPT_BYTES = 500
_EXCERPT_CHARS = 500
_DETAIL_CHARS = 200


def _map_error(exc: Exception, *, label: str = "Vertex") -> ProviderError:
    """Turn a transport exception into a one-line ProviderError."""
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body = exc.read(_EXCERPT_BYTES).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        body = body[:_EXCERPT_CHARS]
        return ProviderError(f"HTTP {exc.code} {body}" if body else f"HTTP {exc.code}")
    name = type(exc).__name__
    # Only transport errors carry a safe reason. ValueError and HTTPException text
    # can contain header values (the API key), so they stay class-name-only.
    if isinstance(exc, urllib.error.URLError):
        return ProviderError(f"{label} request failed: {name}: {_detail(exc.reason)}")
    if isinstance(exc, OSError):
        return ProviderError(f"{label} request failed: {name}: {_detail(exc)}")
    return ProviderError(f"{label} request failed: {name}")


def _detail(value: object) -> str:
    return one_line(str(value))[:_DETAIL_CHARS]


def _post_with(
    url: str,
    headers: dict[str, str],
    body: bytes,
    timeout: float,
    *,
    label: str = "Vertex",
    expect_status: int | None = None,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> bytes:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with opener(request, timeout=timeout) as response:
            status = getattr(response, "status", None)
            if expect_status is not None and status != expect_status:
                raise ProviderError(f"HTTP {status}")
            return response.read()
    except (OSError, http.client.HTTPException, ValueError) as exc:
        raise _map_error(exc, label=label) from exc


def urllib_post(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> bytes:
    """POST body to url and return the raw response bytes."""
    return _post_with(url, headers, body, timeout)
