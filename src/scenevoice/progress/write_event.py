"""Write one progress event to a stream as a single flushed line."""

from typing import Any

from scenevoice.progress.event_line import event_line


def write_event(
    stream: Any, command: str, event: str, message: str, **fields: object
) -> None:
    """Write event_line(...) in one write call, then flush if possible.

    Callers redact and one_line the message first; this does neither.
    """
    stream.write(event_line(command, event, message, **fields))
    flush = getattr(stream, "flush", None)
    if flush is not None:
        flush()
