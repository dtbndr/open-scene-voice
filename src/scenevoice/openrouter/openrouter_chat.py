import http.client
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from scenevoice.openrouter.chat_constants import CHAT_TIMEOUT_SECONDS, CHAT_URL
from scenevoice.openrouter.chat_error import ChatError, ChatTimedOut, ChatUnreachable
from scenevoice.synth.one_line import one_line
from scenevoice.synth.redact_secret import redact_secret

_EXCERPT_CHARS = 500


def _map_error(exc: Exception, key: str) -> ChatError:
    if isinstance(exc, urllib.error.HTTPError):
        try:
            kb = len(key.encode())
            window = _EXCERPT_CHARS * max(4, kb) + kb
            body = exc.read(window).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        text = one_line(redact_secret(body, key))[:_EXCERPT_CHARS]
        return ChatError(exc.code, text)
    name = type(exc).__name__
    # TimeoutError is an OSError: test it (and a URLError wrapping one) first.
    # ValueError and HTTPException text can carry header values (the key), so
    # every non-HTTP failure keeps only its type name.
    if isinstance(exc, TimeoutError) or (
        isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, TimeoutError)
    ):
        return ChatTimedOut(None, name)
    return ChatUnreachable(None, name)


def openrouter_chat(
    body: bytes,
    key: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> bytes:
    """POST one chat request to OpenRouter; return the body of an exact 200 response."""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    request = urllib.request.Request(
        CHAT_URL, data=body, headers=headers, method="POST"
    )
    try:
        with opener(request, timeout=CHAT_TIMEOUT_SECONDS) as response:
            status = response.status
            reply: bytes = response.read()
    except (OSError, http.client.HTTPException, ValueError) as exc:
        raise _map_error(exc, key) from exc
    if status != 200:
        raise ChatError(status, f"HTTP {status}")
    return reply
