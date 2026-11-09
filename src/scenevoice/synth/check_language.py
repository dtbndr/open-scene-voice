from scenevoice.synth.is_text_blank import is_text_blank
from scenevoice.validation import Violation

_RULE = "synth-option"


def check_language(language: str) -> Violation | None:
    """Reject a blank or UTF-8-unencodable language. Never raises."""
    if is_text_blank(language):
        return Violation(_RULE, "language must not be blank")
    try:
        language.encode("utf-8")
    except UnicodeEncodeError:
        return Violation(_RULE, "language cannot be encoded as UTF-8")
    return None
