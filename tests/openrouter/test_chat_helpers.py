"""Tests for `make_openrouter_chat` (no network).

`redact_chat_error`: a copy of the error with every secret removed from its text.
"""

import inspect
import urllib.request

import pytest
from chat_run_helper import KEY
from openrouter_transport_helper import FakeResponse

from scenevoice.openrouter import ChatError, ChatTimedOut
from scenevoice.openrouter.make_openrouter_chat import make_openrouter_chat
from scenevoice.openrouter.redact_chat_error import redact_chat_error

pytestmark = pytest.mark.usefixtures("no_sockets")


def test_construction_makes_no_call():
    calls = []
    make_openrouter_chat(KEY, opener=lambda *a, **k: calls.append(a))
    assert calls == []


def test_key_is_sent_stripped():
    seen = []

    def opener(request, timeout):
        seen.append(request)
        return FakeResponse()

    chat = make_openrouter_chat(f"  {KEY}\n", opener=opener)
    assert chat(b"{}") == b"{}"
    assert seen[0].get_header("Authorization") == f"Bearer {KEY}"
    assert seen[0].data == b"{}"


def test_default_opener_is_real_urlopen():
    default = inspect.signature(make_openrouter_chat).parameters["opener"].default
    assert default is urllib.request.urlopen


def test_every_secret_is_redacted_and_none_is_ignored() -> None:
    error = ChatError(400, "bad first-secret-0001 then later-secret-0002")
    redacted = redact_chat_error(error, [None, "first-secret-0001", "later-secret-0002"])
    assert redacted.text == "bad [redacted] then [redacted]"
    assert error.text == "bad first-secret-0001 then later-secret-0002"


def test_status_and_error_type_are_kept() -> None:
    redacted = redact_chat_error(ChatTimedOut(None, "TimeoutError"), ["x-secret-0001"])
    assert type(redacted) is ChatTimedOut
    assert redacted.status is None
    assert redacted.text == "TimeoutError"
    refused = redact_chat_error(ChatError(402, "no credit"), ["x-secret-0001"])
    assert (type(refused), refused.status) == (ChatError, 402)
