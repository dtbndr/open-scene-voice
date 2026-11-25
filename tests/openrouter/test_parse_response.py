"""Tests for `parse_chat_response` (no network; fixture bodies only)."""

import json

import pytest
from chat_run_helper import synthetic

from scenevoice.openrouter import (
    ChatBlocked,
    ChatOutOfLength,
    ChatUnreadable,
    parse_chat_response,
)

pytestmark = pytest.mark.usefixtures("no_sockets")


def case_body(name):
    body = synthetic(name)["body"]
    if isinstance(body, str):
        return body.encode("utf-8")
    return json.dumps(body).encode("ascii")


def reply(content, finish="stop"):
    choice = {"message": {"content": content}}
    if finish is not None:
        choice["finish_reason"] = finish
    return json.dumps({"choices": [choice]}).encode("utf-8")


def test_good_reply_returns_text_not_truncated():
    text, truncated = parse_chat_response(case_body("good_reply"))
    assert text.strip() and truncated is False


def test_length_returns_text_truncated():
    text, truncated = parse_chat_response(case_body("length_reply"))
    assert text.strip() and truncated is True


def test_length_with_empty_content_is_out_of_length():
    with pytest.raises(ChatOutOfLength) as info:
        parse_chat_response(case_body("length_empty_content_reply"))
    assert isinstance(info.value, ChatUnreadable)


def test_length_with_whitespace_content_is_out_of_length():
    with pytest.raises(ChatOutOfLength):
        parse_chat_response(reply(" \n\t", "length"))


def test_content_filter_is_blocked():
    with pytest.raises(ChatBlocked):
        parse_chat_response(case_body("content_filter_reply"))


@pytest.mark.parametrize(
    "case",
    [
        "non_json_200",
        "empty_choices_reply",
        "error_object_in_200",
        "null_content_reply",
        "lone_surrogate_reply",
    ],
)
def test_unusable_synthetic_bodies_are_unreadable(case):
    with pytest.raises(ChatUnreadable) as info:
        parse_chat_response(case_body(case))
    assert not isinstance(info.value, ChatOutOfLength)


@pytest.mark.parametrize(
    "body",
    [
        reply(""),
        reply(5),
        b"[]",
        b'{"choices": "x"}',
        b'{"choices": [{"message": null}]}',
        b'{"choices": [{}]}',
        b'{"error": "x", "choices": [{"message": {"content": "a"}}]}',
        b"",
    ],
)
def test_wrong_shapes_are_unreadable_without_other_exceptions(body):
    with pytest.raises(ChatUnreadable):
        parse_chat_response(body)


def test_only_first_choice_is_read():
    body = json.dumps(
        {
            "choices": [
                {"message": {"content": "first"}, "finish_reason": "stop"},
                {"message": {"content": "second"}, "finish_reason": "length"},
            ]
        }
    ).encode()
    assert parse_chat_response(body) == ("first", False)


@pytest.mark.parametrize("finish", [None, "tool_calls", "weird", 7])
def test_other_or_missing_finish_reason_is_normal_stop(finish):
    assert parse_chat_response(reply("hi", finish)) == ("hi", False)


def test_error_text_is_a_bounded_excerpt():
    huge = b"x" * 5000
    with pytest.raises(ChatUnreadable) as info:
        parse_chat_response(huge)
    assert len(info.value.text) < 400
    assert huge.decode() not in info.value.text
