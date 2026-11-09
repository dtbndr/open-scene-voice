import json
from urllib.parse import quote


def build_vertex_request(
    project: str,
    location: str,
    key: str,
    body: str,
    voice: str,
    language: str,
    style: str | None,
    model: str,
) -> tuple[str, dict[str, str], bytes]:
    """Build (url, headers, body) for one Vertex generateContent call.

    The body text is sent verbatim. A style, when not None (even empty), rides as
    `speechMetadata.style` beside `text` in the first part; a system instruction
    field is NOT sent (the 3.8 model rejects it). Project and location are
    URL-quoted so they cannot change the path structure. The model rides in the URL
    path only, never in the body.
    """
    url = (
        "https://aiplatform.googleapis.com/v1"
        f"/projects/{quote(project, safe='')}"
        f"/locations/{quote(location, safe='')}"
        f"/publishers/google/models/{model}:generateContent"
    )
    headers = {"X-goog-api-key": key, "Content-Type": "application/json"}
    part: dict[str, object] = {"text": body}
    if style is not None:
        part["speechMetadata"] = {"style": style}
    payload = {
        "contents": [{"role": "user", "parts": [part]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "languageCode": language,
                "voiceConfig": {"voice": voice},
            },
        },
    }
    return url, headers, json.dumps(payload, ensure_ascii=False).encode("utf-8")
