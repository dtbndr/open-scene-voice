import urllib.request
from collections.abc import Callable
from typing import Any

from scenevoice.openrouter.chat_types import Chat
from scenevoice.openrouter.openrouter_chat import openrouter_chat


def make_openrouter_chat(
    key: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> Chat:
    """Build a Chat for the key (stripped); makes no network call."""
    clean = key.strip()

    def chat(body: bytes) -> bytes:
        return openrouter_chat(body, clean, opener=opener)

    return chat
