from scenevoice.synth.provider_registry import PROVIDERS

MODELS = tuple(model for spec in PROVIDERS for model in spec.models)
