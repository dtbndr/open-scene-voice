def plain_int(value: object) -> int | None:
    """The value if it is a real integer (a boolean is not one), else None."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None
