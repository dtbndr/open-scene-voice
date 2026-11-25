import hashlib


def script_revision(data: bytes) -> str:
    """The script revision: SHA-256, 64 lowercase hex characters, of the exact bytes of `script.md`."""
    return hashlib.sha256(data).hexdigest()
