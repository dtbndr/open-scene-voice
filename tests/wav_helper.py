import base64
import io
import json
import wave

from scenevoice.synth import ProviderAudio


def make_wav(frames=10, rate=24000, channels=1, width=2):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(b"\x00" * (frames * channels * width))
    return buf.getvalue()


def wav_audio(frames=10, **kw):
    return ProviderAudio("audio/wav", make_wav(frames, **kw))


def vertex_wav_response(frames=10):
    """Vertex success response bytes carrying a WAV (the 3.8 response side)."""
    data = base64.b64encode(make_wav(frames)).decode("ascii")
    part = {"inlineData": {"mimeType": "audio/wav", "data": data}}
    return json.dumps({"candidates": [{"content": {"parts": [part]}}]}).encode("utf-8")
