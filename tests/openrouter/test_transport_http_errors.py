"""How a failed HTTP response becomes a bounded, redacted `ChatError` (no network)."""

import json

import pytest
from chat_run_helper import KEY, synthetic
from openrouter_transport_helper import (
    BODY,
    FakeOpener,
    chat_error,
    http_error,
    observed,
)

from scenevoice.openrouter import (
    ChatError,
)
from scenevoice.openrouter.openrouter_chat import openrouter_chat

pytestmark = pytest.mark.usefixtures("no_sockets")


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (401, observed("error_401.json")),
        (400, observed("error_400.json")),
        (402, json.dumps(synthetic("error_402")["body"]).encode()),
        (429, json.dumps(synthetic("error_429")["body"]).encode()),
        (500, json.dumps(synthetic("error_500")["body"]).encode()),
    ],
)
def test_http_error_keeps_status_and_one_line_excerpt(status, body):
    error = chat_error(FakeOpener(raises=http_error(status, body)))
    assert type(error) is ChatError
    assert error.status == status
    assert "\n" not in error.text
    assert json.loads(body)["error"]["message"] in error.text


def test_http_error_excerpt_is_bounded_and_redacted():
    body = (b"x" * 5000) + KEY.encode()
    error = chat_error(FakeOpener(raises=http_error(400, body)))
    assert len(error.text) <= 500
    big = chat_error(FakeOpener(raises=http_error(400, f"echo {KEY} here".encode())))
    assert KEY not in big.text


def test_key_after_four_byte_characters_is_read_whole_and_redacted():
    key = "CANARY-key-0123456789"
    body = ("\U0001f600" * 499 + key + "tail").encode()
    with pytest.raises(ChatError) as info:
        openrouter_chat(BODY, key, opener=FakeOpener(raises=http_error(401, body)))
    assert info.value.text == ("\U0001f600" * 499 + "[redacted]tail")[:500]
    assert key[:6] not in info.value.text


def test_body_repeating_the_key_many_times_leaves_no_fragment():
    key = "CANARY-" + "k" * 66
    with pytest.raises(ChatError) as info:
        openrouter_chat(BODY, key, opener=FakeOpener(raises=http_error(401, (key * 31).encode())))
    assert info.value.text == "[redacted]" * 31


def test_http_error_with_unreadable_body_has_empty_text():
    broken = http_error(400, b"")
    broken.read = lambda *a: (_ for _ in ()).throw(OSError("boom"))
    assert chat_error(FakeOpener(raises=broken)).text == ""
