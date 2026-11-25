import secrets


def make_token() -> str:
    """A fresh per-launch token: 32 random bytes, urlsafe."""
    return secrets.token_urlsafe(32)
