"""Split an existing say-style text into a progress event and message."""

_EVENTS = (("FAIL ", "fail"), ("NOTE ", "note"), ("OK ", "ok"))


def split_line(command: str, text: str) -> tuple[str, str]:
    """Return (event, message) for text such as ``FAIL no key``.

    An optional ``scenevoice <command>: `` prefix of the given command is
    stripped first. Raises ValueError for any other text.
    """
    prefix = f"scenevoice {command}: "
    if text.startswith(prefix):
        text = text[len(prefix) :]
    for word, event in _EVENTS:
        if text.startswith(word):
            return event, text[len(word) :]
    raise ValueError(f"not a progress line: {text!r}")
