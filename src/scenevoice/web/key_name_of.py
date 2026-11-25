from scenevoice.keys.key_names import KEY_NAMES

PREFIX = "/api/keys/"


def key_name_of(path: str) -> str | None:
    """The key name in `/api/keys/NAME`, or None unless it is exactly one of KEY_NAMES."""
    name = path[len(PREFIX) :] if path.startswith(PREFIX) else ""
    return name if name in KEY_NAMES else None
