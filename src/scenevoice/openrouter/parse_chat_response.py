import json
from typing import Any

from scenevoice.openrouter.chat_error import (
    ChatBlocked,
    ChatOutOfLength,
    ChatUnreadable,
)


def _first_choice(body: bytes) -> dict[str, Any]:
    try:
        doc = json.loads(body)
    except (ValueError, RecursionError) as exc:
        raise ChatUnreadable(200, "the reply body is not JSON") from exc
    if not isinstance(doc, dict):
        raise ChatUnreadable(200, "the reply body is not a JSON object")
    if "error" in doc:
        raise ChatUnreadable(200, "the reply body carries an error object")
    choices = doc.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ChatUnreadable(200, "the reply has no choices")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise ChatUnreadable(200, "the first choice is not an object")
    return choice


def _content(choice: dict[str, Any]) -> str:
    message = choice.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        return ""
    return content


def parse_chat_response(body: bytes) -> tuple[str, bool]:
    """Return (text, truncated) from the first choice of a 200 body, or raise."""
    choice = _first_choice(body)
    finish = choice.get("finish_reason")
    if finish == "content_filter":
        raise ChatBlocked(200, "the provider withheld the reply")
    text = _content(choice)
    if not text.strip():
        if finish == "length":
            raise ChatOutOfLength(200, "the length limit was hit before any script")
        raise ChatUnreadable(200, "the first choice has no text")
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ChatUnreadable(200, "the reply text is not valid UTF-8") from exc
    return text, finish == "length"
