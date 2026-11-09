def is_blank(text: str) -> bool:
    """True for the empty string and any text made only of Unicode White_Space.

    str.isspace() also accepts U+001C-001F, which are Cc controls already
    rejected by check_controls before any caller sees the text.
    """
    return text == "" or text.isspace()
