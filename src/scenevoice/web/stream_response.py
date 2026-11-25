from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class StreamResponse:
    """A handler's open-ended reply: head with no Content-Length, then each chunk until the iterator ends."""

    status: int
    headers: tuple[tuple[str, str], ...]
    chunks: Iterator[bytes]
    no_store: bool = True
