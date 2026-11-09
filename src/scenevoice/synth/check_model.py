from scenevoice.synth.models import MODELS
from scenevoice.validation import Violation


def check_model(model: str) -> Violation | None:
    """Accept exactly the supported model names (case-sensitive). Never raises."""
    if model in MODELS:
        return None
    return Violation("synth-option", f"model must be one of {', '.join(MODELS)}")
