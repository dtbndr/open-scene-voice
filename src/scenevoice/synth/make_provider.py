from scenevoice.synth.provider import Provider, ProviderError
from scenevoice.synth.provider_registry import provider_for_model


def make_provider(env: dict[str, str], model: str) -> Provider:
    """Dispatch to the factory of the provider that owns `model`."""
    spec = provider_for_model(model)
    if spec is None:
        raise ProviderError(f"no provider for model {model}")
    return spec.factory(env, model)
