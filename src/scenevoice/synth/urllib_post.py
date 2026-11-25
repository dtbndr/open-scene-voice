"""Stdlib HTTP POST transport for the Vertex adapter.

Every failure becomes ProviderError. The transport redacts the credential values
it was given in secret headers from an HTTP error body before cutting the excerpt,
so a key straddling the cut cannot leave a fragment. The real network call is
covered only by WS10 live acceptance; tests exercise `_map_error` and `_post_with`
with locally built errors and a stub opener.
"""

import http.client
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from scenevoice.synth.one_line import one_line
from scenevoice.synth.provider import ProviderError
from scenevoice.synth.redact_secret import redact_secret
from scenevoice.synth.secret_header_values import secret_header_values

_EXCERPT_CHARS = 500
_DETAIL_CHARS = 200


def _map_error(
    exc: Exception, *, label: str = "Vertex", secrets: tuple[str, ...] = ()
) -> ProviderError:
    """Turn a transport exception into a one-line ProviderError."""
    if isinstance(exc, urllib.error.HTTPError):
        # A redacted key shrinks to 10 chars, so each kept char can cost up to
        # max(4, key bytes) read bytes; the extra key bytes read a straddler whole.
        kb = max((len(s.encode()) for s in secrets), default=0)
        window = _EXCERPT_CHARS * max(4, kb) + kb
        try:
            body = exc.read(window).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        for secret in secrets:
            body = redact_secret(body, secret)
        body = body[:_EXCERPT_CHARS]
        message = f"HTTP {exc.code} {body}" if body else f"HTTP {exc.code}"
        return ProviderError(message, status=exc.code)
    name = type(exc).__name__
    # Only transport errors carry a safe reason. ValueError and HTTPException text
    # can contain header values (the API key), so they stay class-name-only.
    if isinstance(exc, urllib.error.URLError):
        return ProviderError(
            f"{label} request failed: {name}: {_detail(exc.reason)}", transport=True
        )
    if isinstance(exc, OSError):
        return ProviderError(
            f"{label} request failed: {name}: {_detail(exc)}", transport=True
        )
    return ProviderError(
        f"{label} request failed: {name}",
        transport=isinstance(exc, http.client.HTTPException)
        and not isinstance(exc, http.client.InvalidURL),
    )


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
                raise ProviderError(f"HTTP {status}", status=status)
            return response.read()
    except (OSError, http.client.HTTPException, ValueError) as exc:
        secrets = tuple(secret_header_values(headers))
        raise _map_error(exc, label=label, secrets=secrets) from exc


def urllib_post(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> bytes:
    """POST body to url and return the raw response bytes."""
    return _post_with(url, headers, body, timeout)
