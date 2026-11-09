"""Vertex AI TTS provider factory.

Joins request building, the injected `post` and response parsing. Every failure
is a ProviderError, and the exact API key is redacted from every message raised.
The real network call is covered only by WS10 live acceptance.
"""

from collections.abc import Callable

from scenevoice.synth.build_vertex_request import build_vertex_request
from scenevoice.synth.parse_vertex_response import parse_vertex_response
from scenevoice.synth.provider import (
    Provider,
    ProviderAudio,
    ProviderError,
    ProviderRequest,
)
from scenevoice.synth.redact_secret import redact_secret
from scenevoice.synth.urllib_post import urllib_post

_TIMEOUT_SECONDS = 180

Post = Callable[[str, dict[str, str], bytes, float], bytes]


def make_vertex_provider(env: dict[str, str], model: str, post: Post = urllib_post) -> Provider:
    project = env["GOOGLE_CLOUD_PROJECT"].strip()
    location = env["GOOGLE_CLOUD_LOCATION"].strip()
    raw_key = env["VERTEX_AUTHORIZATION_KEY"]
    key = raw_key.strip()

    def provider(request: ProviderRequest) -> ProviderAudio:
        if request.language is None:
            raise ProviderError("Vertex request has no language")
        try:
            url, headers, payload = build_vertex_request(
                project, location, key, request.body, request.voice, request.language, request.instruction, model
            )
            return parse_vertex_response(post(url, headers, payload, _TIMEOUT_SECONDS))
        except ProviderError as exc:
            raise ProviderError(redact_secret(str(exc), raw_key)) from exc
        except Exception as exc:
            message = f"Vertex request failed: {type(exc).__name__}"
            raise ProviderError(redact_secret(message, raw_key)) from exc

    return provider
