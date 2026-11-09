import json
from urllib.parse import quote

from scenevoice.synth.provider import ProviderRequest

_SEED = 42


def build_elevenlabs_request(
    key: str, model: str, request: ProviderRequest
) -> tuple[str, dict[str, str], bytes]:
    """Build (url, headers, body) for one ElevenLabs with-timestamps call.

    The body text is sent verbatim. A neighbour is sent only when not None. The voice is
    URL-quoted so it cannot change the path or query. Language and instruction are never sent.
    """
    url = (
        "https://api.elevenlabs.io/v1/text-to-speech/"
        f"{quote(request.voice, safe='')}/with-timestamps?output_format=pcm_24000"
    )
    headers = {"xi-api-key": key, "Content-Type": "application/json"}
    payload: dict[str, object] = {"text": request.body, "model_id": model}
    if request.previous_text is not None:
        payload["previous_text"] = request.previous_text
    if request.next_text is not None:
        payload["next_text"] = request.next_text
    payload["seed"] = _SEED
    return url, headers, json.dumps(payload, ensure_ascii=False).encode("utf-8")
