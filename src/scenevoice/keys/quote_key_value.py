def quote_key_value(value: str) -> str:
    """A single-quoted dotenv token that parses back to exactly `value`: no interpolation,
    and only the backslash and the single quote need escaping in that form."""
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
