from scenevoice.synth.provider import ProviderError


class TranscriptionError(ProviderError):
    """A non-200 or transport failure; status is None for transport/timeout."""

    def __init__(self, status: int | None, text: str) -> None:
        super().__init__(text)
        self.status = status
        self.text = text
