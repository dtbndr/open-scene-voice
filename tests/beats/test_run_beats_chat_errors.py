"""Each chat failure has its own plain line and writes nothing."""


import pytest
from beats_run_helper import (
    PREFIX,
    body_of,
    run,
)
from chat_run_helper import FakeChat

from scenevoice.openrouter import ChatError, ChatTimedOut, ChatUnreachable

pytestmark = pytest.mark.usefixtures("no_sockets")


ERROR_CASES = {
    "reset": (ChatUnreachable(None, "connection reset while reading the reply"),
              "the request to OpenRouter failed (connection reset while reading the reply); "),
    "timeout": (ChatTimedOut(None, "timed out"), "the request to OpenRouter timed out"),
    "e402": (ChatError(402, "no credit"), "the OpenRouter account has no credit left"),
    "e429": (ChatError(429, "slow down"), "too many requests"),
    "e500": (ChatError(500, "boom"), "OpenRouter had a problem; try again in a minute"),
    "e401": (ChatError(401, "bad key"), "OpenRouter did not accept the key; check OPENROUTER_API_KEY"),
}


@pytest.mark.parametrize("name", list(ERROR_CASES))
def test_each_chat_error_gives_its_own_fail_line_and_writes_nothing(tmp_path, name):
    error, start = ERROR_CASES[name]
    fake = FakeChat(error)
    code, err, out = run(tmp_path, fake)
    assert code == 1 and not out.exists()
    assert len(fake.requests) == 1
    lines = err.splitlines()
    assert len(lines) == 1 and lines[0].startswith(PREFIX + "FAIL " + start)
    assert "nothing was charged" not in err


def test_network_failures_say_it_may_still_have_been_charged(tmp_path):
    _, err, _ = run(tmp_path, FakeChat(ERROR_CASES["reset"][0]))
    assert "may still have been charged" in err


def test_unreadable_reply_uses_beats_wording_and_writes_nothing(tmp_path):
    fake = FakeChat(b"<html>gateway</html>")
    code, err, out = run(tmp_path, fake)
    assert code == 1 and not out.exists()
    assert err.splitlines() == [
        f"{PREFIX}FAIL OpenRouter replied, but the reply could not be read as beats"
    ]


def test_content_filter_uses_the_beats_hint(tmp_path):
    body = body_of("", finish="content_filter")
    code, err, out = run(tmp_path, FakeChat(body))
    assert code == 1 and not out.exists()
    assert err.splitlines() == [
        f"{PREFIX}FAIL OpenRouter's content filter stopped the reply; try another model"
    ]


def test_length_with_empty_text_uses_the_beats_hint(tmp_path):
    code, err, out = run(tmp_path, FakeChat(body_of("", finish="length")))
    assert code == 1 and not out.exists()
    assert err.splitlines() == [
        f"{PREFIX}FAIL the reply ran out of length before it held beats; try a shorter script"
    ]
