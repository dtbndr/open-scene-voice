"""Provider registry: one spec per provider (Vertex, ElevenLabs)."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from scenevoice.synth.check_body_bytes import check_body_bytes
from scenevoice.synth.check_body_chars import check_body_chars
from scenevoice.synth.env_names import ELEVENLABS_ENV_NAMES, ENV_NAMES
from scenevoice.synth.make_elevenlabs_provider import make_elevenlabs_provider
from scenevoice.synth.make_vertex_provider import make_vertex_provider
from scenevoice.synth.plan_scene import PlanScene
from scenevoice.synth.provider import ProviderFactory
from scenevoice.synth.voices import VOICES
from scenevoice.validation import Violation

# A body check already bound to its model.
BodyCheck = Callable[[Sequence[PlanScene]], Violation | None]


@dataclass(frozen=True)
class ProviderSpec:
    models: tuple[str, ...]
    voices: tuple[str, ...] | None
    env_names: tuple[str, ...]
    secret_env_name: str
    check_body_limit: Callable[[Sequence[PlanScene], str], Violation | None]  # (scenes, model)
    factory: ProviderFactory


VERTEX = ProviderSpec(
    models=("gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"),
    voices=VOICES,
    env_names=ENV_NAMES,
    secret_env_name="VERTEX_AUTHORIZATION_KEY",
    check_body_limit=check_body_bytes,
    factory=make_vertex_provider,
)

ELEVENLABS = ProviderSpec(
    models=("eleven_flash_v2_5", "eleven_v4"),
    voices=None,
    env_names=ELEVENLABS_ENV_NAMES,
    secret_env_name="ELEVENLABS_API_KEY",
    check_body_limit=check_body_chars,
    factory=make_elevenlabs_provider,
)

PROVIDERS = (VERTEX, ELEVENLABS)


def provider_for_model(model: str) -> ProviderSpec | None:
    """The spec that owns `model` (exact match), or None."""
    for spec in PROVIDERS:
        if model in spec.models:
            return spec
    return None
