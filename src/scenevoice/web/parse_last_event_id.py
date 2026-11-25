import re

_ID = re.compile(r"([0-9]{1,9})-([0-9]{1,9})", re.ASCII)


def parse_last_event_id(value: str | None) -> tuple[int, int] | None:
    """`(job, seq)` from a `Last-Event-ID` header value, or None for anything that is not exactly that."""
    if value is None:
        return None
    match = _ID.fullmatch(value)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))
