import re

from scenevoice.align.white_space import WHITE_SPACE_RUN

_NOT_TOKEN_CHAR = re.compile("[^a-z0-9']")


def word_tokens(text: str) -> list[str]:
    """Reduce text to match tokens: split, lower, strip in place, drop empties."""
    pieces = WHITE_SPACE_RUN.split(text)
    stripped = (_NOT_TOKEN_CHAR.sub("", piece.lower()) for piece in pieces)
    return [token for token in stripped if token]
