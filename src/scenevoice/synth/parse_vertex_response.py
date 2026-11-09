import base64
import json
import re

from scenevoice.synth.provider import ProviderAudio, ProviderError

_REASON = re.compile(r"[A-Za-z_]{1,64}")


def _reason(container: object, key: str) -> str:
    """Return a short enum-like reason as ' (key: VALUE)', else ''. Never echoes other text."""
    value = container.get(key) if isinstance(container, dict) else None
    if isinstance(value, str) and _REASON.fullmatch(value):
        return f" ({key}: {value})"
    return ""


def parse_vertex_response(raw: bytes) -> ProviderAudio:
    """Parse a Vertex generateContent response body into ProviderAudio.

    Takes the first part holding inlineData. MIME acceptance and WAV
    header rules stay in validate_audio. Raises ProviderError with a short message
    that never embeds the response body.
    """
    try:
        doc = json.loads(raw)
    except ValueError:  # JSONDecodeError and UnicodeDecodeError
        raise ProviderError("Vertex response is not valid JSON") from None
    if not isinstance(doc, dict):
        raise ProviderError("Vertex response is not a JSON object")
    candidates = doc.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        reason = _reason(doc.get("promptFeedback"), "blockReason")
        raise ProviderError("Vertex response has no candidates" + reason)
    candidate = candidates[0]
    content = candidate.get("content") if isinstance(candidate, dict) else None
    if not isinstance(content, dict):
        reason = _reason(candidate, "finishReason")
        raise ProviderError("Vertex response candidate has no content" + reason)
    parts = content.get("parts")
    if not isinstance(parts, list):
        raise ProviderError("Vertex response content has no parts")
    for part in parts:
        if not isinstance(part, dict):
            raise ProviderError("Vertex response part is not an object")
        if "inlineData" in part:
            return _audio_from(part["inlineData"])
    raise ProviderError("Vertex response has no inline audio")


def _audio_from(inline: object) -> ProviderAudio:
    if not isinstance(inline, dict):
        raise ProviderError("Vertex response inlineData is not an object")
    mime_type = inline.get("mimeType")
    data = inline.get("data")
    if not isinstance(mime_type, str):
        raise ProviderError("Vertex response mimeType is not a string")
    if not isinstance(data, str):
        raise ProviderError("Vertex response audio data is not a string")
    try:
        wav = base64.b64decode(data, validate=True)
    except ValueError:  # binascii.Error
        raise ProviderError("Vertex response audio data is not valid base64") from None
    return ProviderAudio(mime_type, wav)
