from scenevoice.synth.is_text_blank import is_text_blank
from scenevoice.validation import Violation

_RULE = "synth-option"


def check_instruction(instruction: str) -> Violation | None:
    """Reject a blank or UTF-8-unencodable instruction. Never raises."""
    if is_text_blank(instruction):
        return Violation(_RULE, "instruction must not be blank")
    try:
        instruction.encode("utf-8")
    except UnicodeEncodeError:
        return Violation(_RULE, "instruction cannot be encoded as UTF-8")
    return None
