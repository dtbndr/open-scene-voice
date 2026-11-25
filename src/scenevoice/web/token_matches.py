import hmac


def token_matches(candidate: str, token: str) -> bool:
    """Constant-time compare on bytes; empty or unencodable input is a mismatch, never an error."""
    try:
        candidate_bytes = candidate.encode("ascii")
        token_bytes = token.encode("ascii")
    except UnicodeEncodeError:
        return False
    if not candidate_bytes or not token_bytes:
        return False
    return hmac.compare_digest(candidate_bytes, token_bytes)
