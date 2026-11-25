"""`describe_chat_error`: exact strings for every error class."""

import pytest
from chat_run_helper import KEY
from openrouter_transport_helper import FakeOpener, chat_error, http_error

from scenevoice.openrouter import (
    ChatBlocked,
    ChatError,
    ChatOutOfLength,
    ChatTimedOut,
    ChatUnreachable,
    ChatUnreadable,
    describe_chat_error,
)

pytestmark = pytest.mark.usefixtures("no_sockets")

_CHARGE = "it may still have been charged"
_BEATS = {
    "reply_thing": "beats",
    "too_long_hint": "try a shorter script",
    "blocked_hint": "try another model",
}

# (error, string with the beats wording)
_CASES = [
    (
        ChatTimedOut(None, "TimeoutError"),
        f"the request to OpenRouter timed out waiting for a reply; {_CHARGE} (TimeoutError)",
    ),
    (
        ChatUnreachable(None, "OSError"),
        f"the request to OpenRouter failed (OSError); {_CHARGE}",
    ),
    (
        ChatOutOfLength(200, "length"),
        "the reply ran out of length before it held beats; try a shorter script",
    ),
    (
        ChatUnreadable(200, "no choices"),
        "OpenRouter replied, but the reply could not be read as beats",
    ),
    (
        ChatBlocked(200, "filter"),
        "OpenRouter's content filter stopped the reply; try another model",
    ),
    (
        ChatError(401, "x"),
        "OpenRouter did not accept the key; check OPENROUTER_API_KEY",
    ),
    (ChatError(402, "x"), "the OpenRouter account has no credit left"),
    (
        ChatError(429, "x"),
        "too many requests, or the allowance is used up; wait and retry",
    ),
    (ChatError(500, "x"), "OpenRouter had a problem; try again in a minute"),
    (ChatError(503, "x"), "OpenRouter had a problem; try again in a minute"),
    (
        ChatError(400, "Model does not exist"),
        "OpenRouter refused the request (HTTP 400): Model does not exist",
    ),
]


@pytest.mark.parametrize(("error", "expected"), _CASES)
def test_describe_strings(error, expected):
    assert describe_chat_error(error, **_BEATS) == expected


def described(error):
    return describe_chat_error(error, **_BEATS)


def test_describe_branches_on_type_not_text():
    # Subclasses carry text that looks like their parent; a wrong order shows.
    assert described(ChatTimedOut(None, "URLError")) == described(
        ChatTimedOut(None, "TimeoutError")
    ).replace("TimeoutError", "URLError")
    assert "timed out" in described(ChatTimedOut(None, "ConnectionRefusedError"))
    assert "timed out" not in described(ChatUnreachable(None, "TimeoutError"))
    out_of_length = described(ChatOutOfLength(None, "reply could not be read"))
    unreadable = described(ChatUnreadable(None, "length"))
    assert out_of_length != unreadable
    assert "length" in out_of_length or "long" in out_of_length
    assert described(ChatError(401, "payment required 402")) == described(
        ChatError(401, "")
    )
    assert described(ChatError(400, "no credit left")) != described(ChatError(402, ""))


def test_describe_never_contains_key_from_mapped_error():
    error = chat_error(FakeOpener(raises=http_error(400, f"echo {KEY}".encode())))
    assert KEY not in described(error)


def test_refusal_excerpt_is_cut_at_200_characters():
    assert described(ChatError(400, "x" * 300)) == (
        "OpenRouter refused the request (HTTP 400): " + "x" * 200
    )
