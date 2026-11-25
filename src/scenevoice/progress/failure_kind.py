"""Classify a provider failure into a progress kind from its status alone."""


def failure_kind(provider: str, status: int | None, *, transport: bool = False) -> str:
    """Return the KINDS value for a provider failure.

    provider is "tts" (Vertex and ElevenLabs) or "openrouter". The table uses
    statuses only; response bodies are never parsed.

    Mapping: 401 and 403 are bad_key; 429 is quota; 402 is quota for
    openrouter and other for tts; 500 and up is provider_down; no status with
    transport True is provider_down, with transport False is other; every
    other status (other 4xx, 2xx, 3xx) is other.

    Observed: ElevenLabs 401 invalid_api_key, 402 paid_plan_required, 404
    voice_not_found; OpenRouter 401 and 400. Documented, not observed: Vertex
    429, 403, 404 and 400, and any 429 or 5xx. The M14 live acceptance checks
    the ElevenLabs 401 quota_exceeded body and the Vertex 404, 400, 403 and 429
    bodies.
    """
    if status is None:
        return "provider_down" if transport else "other"
    if status in (401, 403):
        return "bad_key"
    if status == 429:
        return "quota"
    if status == 402:
        return "quota" if provider == "openrouter" else "other"
    if status >= 500:
        return "provider_down"
    return "other"
