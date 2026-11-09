from collections.abc import Callable

Transcriber = Callable[[bytes], bytes]
"""(WAV bytes) -> raw 200 response body; raises TranscriptionError otherwise."""

TranscriberFactory = Callable[[str], Transcriber]
"""(API key) -> Transcriber; makes no network call."""
