import re

AUDIO_NAME = re.compile(r"[0-9]{3,6}\.wav")


def audio_file_name(name: str) -> bool:
    """True when `name` is a synth WAV name (`NNN.wav`, three to six digits); the one allowlist for audio files."""
    return AUDIO_NAME.fullmatch(name) is not None
