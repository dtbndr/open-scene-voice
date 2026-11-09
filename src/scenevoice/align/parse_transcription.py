import json

from scenevoice.align.seconds_to_ms import seconds_to_ms
from scenevoice.align.word_tokens import word_tokens


def parse_transcription(body: bytes) -> list[tuple[str, float]] | str:
    """Validate a 200 body; return (token, start seconds) pairs or a reason."""
    try:
        document = json.loads(body)
    except (ValueError, RecursionError):  # not JSON, bad UTF-8, huge integer
        return "response is not JSON"
    if not isinstance(document, dict):
        return "response is not a JSON object"
    words = document.get("words")
    if not isinstance(words, list) or not words:
        return "response has no words array"
    heard: list[tuple[str, float]] = []
    previous: float | None = None
    for entry in words:
        if not isinstance(entry, dict):
            return "a words entry is not an object"
        word = entry.get("word")
        if not isinstance(word, str):
            return "a words entry has a word that is not a string"
        start = entry.get("start")
        if isinstance(start, bool) or not isinstance(start, (int, float)):
            return "a words entry has a start that is missing or not a number"
        if start < 0:
            return "a words entry has a negative start"
        if seconds_to_ms(start) is None:
            return "a words entry has a start that is not finite or too large"
        if previous is not None and start < previous:
            return "word starts decrease"
        previous = start
        heard.extend((token, float(start)) for token in word_tokens(word))
    if not heard:
        return "response has no words after normalisation"
    return heard
