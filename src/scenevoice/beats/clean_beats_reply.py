"""Mechanical cleanup of a beats reply before parsing (WS35 decision 6)."""

_FENCE = "```"


def clean_beats_reply(text: str) -> tuple[str, list[str]]:
    """Strip a leading BOM and one code fence opening the reply (after blank lines).

    Text after the closing fence is dropped, with a label when it is not blank.

    Returns the cleaned text and a short label for each change made.
    """
    labels: list[str] = []
    if text.startswith("﻿"):
        text = text[1:]
        labels.append("removed a leading byte order mark")
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if line.strip()), None)
    if start is None or not lines[start].startswith(_FENCE):
        return text, labels
    close = next(
        (i for i in range(start + 1, len(lines)) if lines[i].strip() == _FENCE), None
    )
    if close is None:
        return text, labels
    trailing = "\n".join(lines[close + 1 :])
    text = "\n".join(lines[start + 1 : close])
    labels.append("removed a code fence around the whole reply")
    if trailing.strip():
        labels.append("dropped text after the closing code fence")
    return text, labels
