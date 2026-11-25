from collections.abc import Callable
from dataclasses import dataclass

from scenevoice.synth.alignment import Alignment


@dataclass(frozen=True)
class ProviderAudio:
    """One provider response: declared MIME type and decoded WAV bytes."""

    mime_type: str
    wav: bytes
    alignment: Alignment | None = None


class ProviderError(Exception):
    """Provider, JSON or base64 failure; carries its message.

    `status` is the HTTP status when there was one; `transport` is true when no
    HTTP response arrived (connection, timeout, protocol failure).
    """

    def __init__(
        self, message: str = "", *, status: int | None = None, transport: bool = False
    ) -> None:
        super().__init__(message)
        self.status = status
        self.transport = transport


@dataclass(frozen=True)
class ProviderRequest:
    """One scene's request: its body, the neighbouring bodies (None at the ends) and the settings."""

    body: str
    previous_text: str | None
    next_text: str | None
    voice: str
    language: str | None
    instruction: str | None


Provider = Callable[[ProviderRequest], ProviderAudio]
ProviderFactory = Callable[[dict[str, str], str], Provider]  # (env, model) -> provider
