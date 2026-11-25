def valid_text(value: object) -> bool:
    """A creator text value: a string of 1 to 1000 characters with no NUL."""
    return isinstance(value, str) and 1 <= len(value) <= 1000 and "\x00" not in value
