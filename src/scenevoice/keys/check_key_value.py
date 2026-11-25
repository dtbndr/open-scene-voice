def check_key_value(name: str, raw_value: str) -> str | None:
    """None when `raw_value` can be stored, else a message naming `name` and the rule.
    The message never carries the value or any part of it."""
    if raw_value == "":
        return f"{name}: the value is empty"
    if "\n" in raw_value or "\r" in raw_value:
        return f"{name}: the value must not contain a line break"
    if "\x00" in raw_value:
        return f"{name}: the value must not contain a NUL character"
    if raw_value.strip() == "":
        return f"{name}: the value is blank"
    return None
