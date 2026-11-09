import io
import wave

_RATE = 24000
_CHANNELS = 1
_WIDTH = 2  # bytes per sample (16-bit)


def read_wav_frames(data: bytes | bytearray) -> int | str:
    """Check WAV bytes are 24000 Hz, mono, 16-bit, non-empty, complete frames.

    Returns the frame count (an int) when acceptable, otherwise a reason (a str). Never raises.
    """
    try:
        with wave.open(io.BytesIO(data), "rb") as reader:
            rate, channels, width = reader.getframerate(), reader.getnchannels(), reader.getsampwidth()
            frames = reader.getnframes()
            present = len(reader.readframes(frames))
    except Exception:  # wave raises assorted types (RuntimeError, struct.error) on hostile bytes
        return "audio is not a readable WAV file"
    if rate != _RATE:
        return "rate must be exactly 24000"
    if channels != _CHANNELS:
        return "audio must be mono"
    if width != _WIDTH:
        return "audio must be 16-bit"
    if frames <= 0:
        return "audio is empty"
    if present != frames * channels * width:
        return "audio is truncated"
    return frames
