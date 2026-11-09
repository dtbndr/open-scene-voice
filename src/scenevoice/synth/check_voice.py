from scenevoice.synth.is_text_blank import is_text_blank
from scenevoice.synth.voices import VOICES
from scenevoice.validation import Violation

_RULE = "synth-option"


def check_voice(voice: str, voices: tuple[str, ...] | None = VOICES) -> Violation | None:
    """Accept a listed voice name (case-sensitive), or with `voices=None` any non-blank encodable ID."""
    if voices is not None:
        if voice in voices:
            return None
        return Violation(_RULE, "voice must be one of the 30 prebuilt voices (see the synth contract)")
    if is_text_blank(voice):
        return Violation(_RULE, "voice must not be blank")
    try:
        voice.encode("utf-8")
    except UnicodeEncodeError:
        return Violation(_RULE, "voice cannot be encoded as UTF-8")
    return None
