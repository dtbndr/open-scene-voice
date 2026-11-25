"""The key and the script text never reach stderr or stdout."""


import pytest
from beats_run_helper import (
    GOOD,
    PREFIX,
    replying,
    run,
)
from chat_run_helper import KEY, FakeChat

from scenevoice.openrouter import ChatError, ChatTimedOut, ChatUnreachable

pytestmark = pytest.mark.usefixtures("no_sockets")


def test_key_planted_in_exception_4xx_body_and_reply_never_leaks(tmp_path):
    for sub, fake in (
        ("exc", FakeChat(ChatUnreachable(None, f"failed with {KEY} in it"))),
        ("body", FakeChat(ChatError(400, f"bad request {KEY}"))),
        ("reply", replying(f"here is {KEY} not json")),
        ("note", replying({"scenes": [{"scene": 1, "beats": [{"first": 1, "last": 2, "note": KEY}]},
                                      GOOD["scenes"][1]]})),
    ):
        folder = tmp_path / sub
        folder.mkdir()
        code, err, _ = run(folder, fake)
        assert code == (0 if sub == "note" else 1)
        assert KEY not in err and KEY not in run.stdout.getvalue()


def test_reply_text_and_script_text_never_reach_stderr(tmp_path):
    code, err, _ = run(tmp_path, replying("SECRET-REPLY-TEXT is not json"))
    assert "SECRET-REPLY-TEXT" not in err
    assert "First one" not in err


def _key_prefixes_absent(text):
    return all(KEY[:n] not in text for n in range(4, len(KEY) + 1))


@pytest.mark.parametrize("lead", [0, 100, 190, 195], ids=["start", "middle", "straddle-cut", "late"])
def test_key_in_a_4xx_body_is_fully_redacted_across_the_excerpt_cut(tmp_path, lead):
    body = "x" * lead + KEY + "y" * 50
    code, err, _ = run(tmp_path, FakeChat(ChatError(400, body)))
    assert code == 1
    expected = ("x" * lead + "[redacted]" + "y" * 50)[:200]
    assert err.splitlines() == [
        f"{PREFIX}FAIL OpenRouter refused the request (HTTP 400): {expected}"
    ]
    assert _key_prefixes_absent(err)


def test_key_straddling_the_cut_in_a_timeout_text_is_redacted(tmp_path):
    code, err, _ = run(tmp_path, FakeChat(ChatTimedOut(None, "x" * 5 + KEY)))
    assert KEY[:4] not in err
    assert err.splitlines() == [
        f"{PREFIX}FAIL the request to OpenRouter timed out waiting for a reply; "
        "it may still have been charged (xxxxx[redacted])"
    ]


def test_key_resolved_from_the_dotenv_file_is_redacted_too(tmp_path):
    dotenv_key = "dotenv-key-for-tests-0002"
    dotenv = tmp_path / "dotenv"
    dotenv.write_text(f"OPENROUTER_API_KEY={dotenv_key}\n")
    fake = FakeChat(ChatUnreachable(None, f"failed with {dotenv_key} in it"))
    code, err, _ = run(tmp_path, fake, env={}, dotenv=dotenv)
    assert fake.keys == [dotenv_key]
    assert code == 1
    assert dotenv_key not in err
    assert "failed with" in err
