import re

_BREAKS = re.compile(r"[\r\n]+")


def one_line(text: str) -> str:
    """Collapse each run of CR/LF characters to a single space."""
    return _BREAKS.sub(" ", text)
