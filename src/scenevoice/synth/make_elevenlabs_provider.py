"""ElevenLabs TTS provider factory.

Joins request building, the injected `post` and response parsing. Every failure
is a ProviderError, and the exact API key is redacted from every message raised.
The real network call is covered only by live acceptance.
"""

from collections.abc import Callable

from scenevoice.synth.build_elevenlabs_request import build_elevenlabs_request
from scenevoice.synth.elevenlabs_post import elevenlabs_post
from scenevoice.synth.parse_elevenlabs_response import parse_elevenlabs_response
from scenevoice.synth.provider import (
    Provider,
    ProviderAudio,
    ProviderError,
    ProviderRequest,
)
from scenevoice.synth.redact_secret import redact_secret

_TIMEOUT_SECONDS = 180

Post = Callable[[str, dict[str, str], bytes, float], bytes]


def make_elevenlabs_provider(
    env: dict[str, str], model: str, post: Post = elevenlabs_post
) -> Provider:
    raw_key = env["ELEVENLABS_API_KEY"]
    key = raw_key.strip()

    def provider(request: ProviderRequest) -> ProviderAudio:
        try:
            url, headers, payload = build_elevenlabs_request(key, model, request)
            return parse_elevenlabs_response(
                post(url, headers, payload, _TIMEOUT_SECONDS)
            )
        except ProviderError as exc:
            raise ProviderError(redact_secret(str(exc), raw_key)) from exc
        except Exception as exc:
            message = f"ElevenLabs request failed: {type(exc).__name__}"
            raise ProviderError(redact_secret(message, raw_key)) from exc

    return provider
