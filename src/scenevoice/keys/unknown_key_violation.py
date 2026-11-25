from scenevoice.validation import Violation


def unknown_key_violation(name: str) -> Violation:
    """The refusal for a name outside KEY_NAMES. Carries the name only."""
    return Violation("key-file", f"{name} is not a key SceneVoice uses")
