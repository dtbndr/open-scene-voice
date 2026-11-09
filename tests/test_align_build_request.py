import base64
import json

from scenevoice.align.build_transcription_request import build_transcription_request

WAV = b"RIFF\x00\x01\xff\xfe-binary-bytes"


def _body() -> dict:
    return json.loads(build_transcription_request(WAV))


def test_exact_keys() -> None:
    assert set(_body()) == {
        "model",
        "input_audio",
        "language",
        "response_format",
        "timestamp_granularities",
    }


def test_constant_fields() -> None:
    body = _body()
    assert body["model"] == "openai/whisper-large-v3-turbo"
    assert body["language"] == "en"
    assert body["response_format"] == "verbose_json"
    assert body["timestamp_granularities"] == ["word", "segment"]


def test_input_audio_shape_and_round_trip() -> None:
    audio = _body()["input_audio"]
    assert set(audio) == {"data", "format"}
    assert audio["format"] == "wav"
    assert not audio["data"].startswith("data:")
    assert base64.b64decode(audio["data"], validate=True) == WAV


def test_returns_bytes() -> None:
    assert isinstance(build_transcription_request(WAV), bytes)
