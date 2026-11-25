from dataclasses import dataclass


@dataclass(frozen=True)
class Response:
    """What a handler returns; the writer adds Content-Length, Connection and the security headers."""

    status: int
    body: bytes = b""
    headers: tuple[tuple[str, str], ...] = ()
    no_store: bool = False
