from scenevoice.validation.is_blank import is_blank

# str.isspace() accepts U+001C-001F, which are not Unicode White_Space.
_SEPARATOR_CONTROLS = "\u001c\u001d\u001e\u001f"


def is_text_blank(text: str) -> bool:
    """The only blank rule in synth: empty or White_Space-only text."""
    if any(ch in text for ch in _SEPARATOR_CONTROLS):
        return False
    return is_blank(text)
