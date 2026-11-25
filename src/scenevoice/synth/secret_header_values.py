_SECRET_HEADERS = frozenset({"xi-api-key", "x-goog-api-key", "authorization"})
_BEARER = "Bearer "


def secret_header_values(headers: dict[str, str]) -> list[str]:
    """Return the credential values carried by the known secret headers.

    An Authorization value also yields the bare token after its `Bearer ` prefix,
    because an error body echoes the token, not the prefix.
    """
    values: list[str] = []
    for name, value in headers.items():
        if name.lower() not in _SECRET_HEADERS:
            continue
        values.append(value)
        if value.startswith(_BEARER):
            values.append(value[len(_BEARER) :])
    return values
