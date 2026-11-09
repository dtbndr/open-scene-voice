import urllib.request
from collections.abc import Callable
from typing import Any

from scenevoice.align.openrouter_transcriber import openrouter_transcriber
from scenevoice.align.transcriber import Transcriber


def make_openrouter_transcriber(
    key: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> Transcriber:
    """Build a Transcriber for the key (stripped); makes no network call."""
    clean = key.strip()

    def transcribe(wav: bytes) -> bytes:
        return openrouter_transcriber(wav, clean, opener=opener)

    return transcribe
