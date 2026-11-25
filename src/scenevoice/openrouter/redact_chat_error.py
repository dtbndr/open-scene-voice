from scenevoice.openrouter.chat_error import ChatError
from scenevoice.synth import redact_secret


def redact_chat_error(error: ChatError, secrets: list[str | None]) -> ChatError:
    """A copy of the error whose text holds no secret, so any later excerpt cannot cut one in half."""
    text = error.text
    for secret in secrets:
        text = redact_secret(text, secret)
    return type(error)(error.status, text)
