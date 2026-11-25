from scenevoice.openrouter.chat_error import ChatBlocked, ChatError, ChatUnreadable
from scenevoice.progress import failure_kind


def chat_error_kind(error: ChatError) -> str:
    """The progress kind of a chat failure; the subclasses that describe a reply are `other`."""
    if isinstance(error, (ChatUnreadable, ChatBlocked)):  # ChatOutOfLength is a ChatUnreadable
        return "other"
    return failure_kind("openrouter", error.status, transport=error.transport)
