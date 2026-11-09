from scenevoice.validation import Violation

_RULE = "synth-option"


def check_elevenlabs_options(language: str | None, instruction: str | None) -> Violation | None:
    """Reject any present language, then any present instruction (blank or not). Never raises."""
    if language is not None:
        return Violation(_RULE, "--language is not supported with an ElevenLabs model")
    if instruction is not None:
        return Violation(_RULE, "--instruction is not supported with an ElevenLabs model")
    return None
