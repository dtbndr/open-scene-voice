from scenevoice.synth.audio_dir import AUDIO_DIR
from scenevoice.synth.wav_name import wav_name


def audio_rel_path(ordinal: int) -> str:
    """Relative path `audio/NNN.wav` (literal forward slash on every platform)."""
    return f"{AUDIO_DIR}/{wav_name(ordinal)}"
