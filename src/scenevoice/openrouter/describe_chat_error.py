from scenevoice.openrouter.chat_error import (
    ChatBlocked,
    ChatError,
    ChatOutOfLength,
    ChatTimedOut,
    ChatUnreachable,
    ChatUnreadable,
)

_EXCERPT_CHARS = 200
_CHARGE_NOTE = "it may still have been charged"


def describe_chat_error(
    error: ChatError, *, reply_thing: str, too_long_hint: str, blocked_hint: str
) -> str:
    """Plain-words line for a chat failure; branches on type, subclasses first."""
    if isinstance(error, ChatTimedOut):
        return f"the request to OpenRouter timed out waiting for a reply; {_CHARGE_NOTE} ({error.text})"
    if isinstance(error, ChatUnreachable):
        return f"the request to OpenRouter failed ({error.text}); {_CHARGE_NOTE}"
    if isinstance(error, ChatOutOfLength):
        return f"the reply ran out of length before it held {reply_thing}; {too_long_hint}"
    if isinstance(error, ChatUnreadable):
        return f"OpenRouter replied, but the reply could not be read as {reply_thing}"
    if isinstance(error, ChatBlocked):
        return f"OpenRouter's content filter stopped the reply; {blocked_hint}"
    status = error.status
    if status == 401:
        return "OpenRouter did not accept the key; check OPENROUTER_API_KEY"
    if status == 402:
        return "the OpenRouter account has no credit left"
    if status == 429:
        return "too many requests, or the allowance is used up; wait and retry"
    if status is not None and status >= 500:
        return "OpenRouter had a problem; try again in a minute"
    return (
        f"OpenRouter refused the request (HTTP {status}): {error.text[:_EXCERPT_CHARS]}"
    )
