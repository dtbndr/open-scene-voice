"""The request `openrouter_chat` sends and which statuses count as a reply (no network)."""

import inspect
import urllib.error
import urllib.request

import pytest
from chat_run_helper import KEY
from openrouter_transport_helper import (
    BODY,
    FakeOpener,
    FakeResponse,
    chat_error,
)

from scenevoice.openrouter import (
    ChatBlocked,
    ChatError,
    ChatOutOfLength,
    ChatTimedOut,
    ChatUnreachable,
    ChatUnreadable,
)
from scenevoice.openrouter.chat_constants import CHAT_TIMEOUT_SECONDS, CHAT_URL
from scenevoice.openrouter.openrouter_chat import openrouter_chat
from scenevoice.synth.provider import ProviderError

pytestmark = pytest.mark.usefixtures("no_sockets")


def test_default_opener_is_real_urlopen():
    default = inspect.signature(openrouter_chat).parameters["opener"].default
    assert default is urllib.request.urlopen


def test_request_shape():
    opener = FakeOpener(FakeResponse())
    openrouter_chat(BODY, KEY, opener=opener)
    ((request, timeout),) = opener.calls
    assert request.full_url == CHAT_URL
    assert request.get_method() == "POST"
    assert request.data == BODY
    assert request.get_header("Authorization") == f"Bearer {KEY}"
    assert request.get_header("Content-type") == "application/json"
    assert timeout == CHAT_TIMEOUT_SECONDS


def test_exact_200_returns_body_bytes():
    assert (
        openrouter_chat(BODY, KEY, opener=FakeOpener(FakeResponse(200, b"abc")))
        == b"abc"
    )


@pytest.mark.parametrize("status", [201, 206, 204, 302])
def test_other_success_statuses_are_errors(status):
    error = chat_error(FakeOpener(FakeResponse(status, b"abc")))
    assert type(error) is ChatError
    assert error.status == status


def test_chat_error_is_a_provider_error_with_status_and_text():
    error = ChatError(402, "text")
    assert isinstance(error, ProviderError)
    assert (error.status, error.text) == (402, "text")


def test_unreadable_blocked_and_out_of_length_subclass_chat_error():
    assert issubclass(ChatUnreadable, ChatError)
    assert issubclass(ChatOutOfLength, ChatUnreadable)
    assert issubclass(ChatBlocked, ChatError)
    assert issubclass(ChatTimedOut, ChatUnreachable)
