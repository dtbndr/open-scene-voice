import io
import wave


def pcm_to_wav(pcm: bytes) -> bytes:
    """Wrap raw 24000 Hz mono 16-bit little-endian PCM in a standard WAV container."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(24000)
        writer.writeframes(pcm)
    return buffer.getvalue()
