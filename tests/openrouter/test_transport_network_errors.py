"""How a network failure becomes a `ChatUnreachable` or `ChatTimedOut` with a type-name-only text (no network)."""

import http.client
import socket
import urllib.error
import urllib.request

import pytest
from chat_run_helper import KEY
from openrouter_transport_helper import (
    FakeOpener,
    FakeResponse,
    chat_error,
)

from scenevoice.openrouter import (
    ChatTimedOut,
    ChatUnreachable,
)

pytestmark = pytest.mark.usefixtures("no_sockets")


@pytest.mark.parametrize(
    "exc",
    [
        urllib.error.URLError(ConnectionRefusedError("refused")),
        urllib.error.URLError(socket.gaierror(8, "no name")),
        ConnectionRefusedError("refused"),
        OSError("network is down"),
    ],
)
def test_network_failures_are_unreachable_not_timed_out(exc):
    error = chat_error(FakeOpener(raises=exc))
    assert type(error) is ChatUnreachable
    assert error.status is None


@pytest.mark.parametrize(
    "exc",
    [TimeoutError("timed out"), urllib.error.URLError(TimeoutError("timed out"))],
)
def test_timeouts_are_timed_out(exc):
    error = chat_error(FakeOpener(raises=exc))
    assert type(error) is ChatTimedOut
    assert isinstance(error, ChatUnreachable)
    assert error.status is None


def test_network_error_text_is_exception_type_only():
    error = chat_error(FakeOpener(raises=OSError(f"boom {KEY}")))
    assert error.text == "OSError"
    url_error = chat_error(FakeOpener(raises=urllib.error.URLError(f"boom {KEY}")))
    assert url_error.text == "URLError"
    timeout = chat_error(FakeOpener(raises=TimeoutError(f"slow {KEY}")))
    assert timeout.text == "TimeoutError"


def test_reset_while_reading_is_unreachable():
    response = FakeResponse(read_error=ConnectionResetError(f"reset {KEY}"))
    error = chat_error(FakeOpener(response))
    assert type(error) is ChatUnreachable
    assert error.text == "ConnectionResetError"


@pytest.mark.parametrize(
    "exc",
    [ValueError(f"bad header {KEY}"), http.client.HTTPException(f"bad {KEY}")],
)
def test_value_and_http_exceptions_yield_type_name_only(exc):
    error = chat_error(FakeOpener(raises=exc))
    assert KEY not in error.text
    assert error.text == type(exc).__name__
    assert type(error) is ChatUnreachable


def test_errors_chain_the_cause():
    exc = OSError("x")
    assert chat_error(FakeOpener(raises=exc)).__cause__ is exc
