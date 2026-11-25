"""Hash of the exact script bytes a beats sidecar was made from."""

import hashlib


def hash_script_bytes(data: bytes) -> str:
    """Return the lowercase SHA-256 hex digest of `data`."""
    return hashlib.sha256(data).hexdigest()
