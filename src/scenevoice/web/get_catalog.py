from scenevoice.synth import DEFAULT_LANGUAGE, PROVIDERS

from .json_response import json_response
from .request import Request
from .response import Response
from .route_table import Handler

PROVIDER_IDS = ("vertex", "elevenlabs")  # the registry has no name field; these follow PROVIDERS' order


def get_catalog() -> dict[str, dict[str, Handler]]:
    """GET /api/catalog: per provider id its models, env names and voices (None when the voice is a pasted ID), plus the default language."""

    def handle(request: Request) -> Response:
        providers = {
            name: {"models": list(spec.models), "env_names": list(spec.env_names), "voices": None if spec.voices is None else list(spec.voices)}
            for name, spec in zip(PROVIDER_IDS, PROVIDERS, strict=True)
        }
        return json_response(200, {"providers": providers, "default_language": DEFAULT_LANGUAGE})

    return {"/api/catalog": {"GET": handle}}
