from scenevoice.synth.provider import ProviderError


class ChatError(ProviderError):
    """A non-200 or transport failure; status is None for transport/timeout."""

    def __init__(self, status: int | None, text: str) -> None:
        super().__init__(text, transport=(status is None))
        self.status = status
        self.text = text


class ChatUnreachable(ChatError):
    """Any other network failure, including a reset while reading; may be charged."""


class ChatTimedOut(ChatUnreachable):
    """Timed out waiting for the reply; may be charged."""


class ChatUnreadable(ChatError):
    """A 200 whose body cannot be used as a reply."""


class ChatOutOfLength(ChatUnreadable):
    """The length limit was hit and there is no reply text."""


class ChatBlocked(ChatError):
    """The provider's content filter stopped the reply."""
