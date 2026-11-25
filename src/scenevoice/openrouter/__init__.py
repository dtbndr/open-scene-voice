"""Shared OpenRouter chat pieces: error family, transport, response parser, error describer."""

from scenevoice.openrouter.chat_constants import (
    CHAT_ENV_NAMES,
    CHAT_TIMEOUT_SECONDS,
    CHAT_URL,
)
from scenevoice.openrouter.chat_error import (
    ChatBlocked,
    ChatError,
    ChatOutOfLength,
    ChatTimedOut,
    ChatUnreachable,
    ChatUnreadable,
)
from scenevoice.openrouter.chat_types import Chat, ChatFactory
from scenevoice.openrouter.describe_chat_error import describe_chat_error
from scenevoice.openrouter.make_openrouter_chat import make_openrouter_chat
from scenevoice.openrouter.openrouter_chat import openrouter_chat
from scenevoice.openrouter.parse_chat_response import parse_chat_response

__all__ = [
    "CHAT_ENV_NAMES",
    "CHAT_TIMEOUT_SECONDS",
    "CHAT_URL",
    "Chat",
    "ChatFactory",
    "ChatBlocked",
    "ChatError",
    "ChatOutOfLength",
    "ChatTimedOut",
    "ChatUnreachable",
    "ChatUnreadable",
    "describe_chat_error",
    "make_openrouter_chat",
    "openrouter_chat",
    "parse_chat_response",
]
