PLACEHOLDER = "[redacted]"


def redact_secret(message: str, secret: str | None) -> str:
    """Backstop: replace the raw secret and its stripped form. A blank secret changes nothing."""
    if secret is None or not secret.strip():
        return message
    for form in sorted({secret, secret.strip()}, key=len, reverse=True):
        message = message.replace(form, PLACEHOLDER)
    return message
