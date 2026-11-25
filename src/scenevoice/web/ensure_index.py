from .placeholder_index import PLACEHOLDER_INDEX


def ensure_index(allowlist: dict[str, bytes]) -> dict[str, bytes]:
    """Return the allowlist with a built-in placeholder as index.html when the UI build has none (display only)."""
    if "index.html" in allowlist:
        return allowlist
    return {**allowlist, "index.html": PLACEHOLDER_INDEX}
