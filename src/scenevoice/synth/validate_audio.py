import re

from scenevoice.synth.one_line import one_line
from scenevoice.synth.provider import ProviderAudio
from scenevoice.synth.read_wav_frames import read_wav_frames
from scenevoice.validation import Violation

_ECHO_MAX = 40
_UNSAFE = re.compile(r"[^A-Za-z0-9/;=.+_ -]")


def _bad(why: str) -> Violation:
    return Violation("synth-response", f"provider response rejected: {why}")


def _echo(mime: object) -> str:
    """The received media type, made one line, ASCII-safe and short for a message."""
    if not isinstance(mime, str):
        return "non-text"
    text = _UNSAFE.sub("?", one_line(mime)).strip()
    if not text:
        return "empty"
    return text if len(text) <= _ECHO_MAX else text[:_ECHO_MAX] + "..."


def validate_audio(audio: ProviderAudio) -> Violation | None:
    """Accept only audio/wav holding 24000 Hz, mono, 16-bit, non-empty, complete frames. Never raises."""
    mime = audio.mime_type
    if not isinstance(mime, str) or mime.partition(";")[0].strip().lower() != "audio/wav":
        return _bad(f"media type must be audio/wav (got {_echo(mime)})")
    data = audio.wav
    if not isinstance(data, (bytes, bytearray)):
        return _bad("audio is not WAV data")
    result = read_wav_frames(data)
    if isinstance(result, str):
        return _bad(result)
    return None
