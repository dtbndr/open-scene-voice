import base64
import json

from scenevoice.align.match_constants import ALIGN_LANGUAGE, ALIGN_MODEL


def build_transcription_request(wav: bytes) -> bytes:
    """Return the JSON request body bytes for one scene's WAV."""
    body = {
        "model": ALIGN_MODEL,
        "input_audio": {"data": base64.b64encode(wav).decode("ascii"), "format": "wav"},
        "language": ALIGN_LANGUAGE,
        "response_format": "verbose_json",
        "timestamp_granularities": ["word", "segment"],
    }
    return json.dumps(body).encode("utf-8")
