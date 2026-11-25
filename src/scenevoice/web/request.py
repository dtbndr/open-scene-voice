from collections.abc import Callable
from dataclasses import dataclass


def no_body(count: int) -> bytes:
    return b""


@dataclass(frozen=True)
class Request:
    """One parsed HTTP request; `path` is the raw path (never percent-decoded) and header names are lowercase."""

    method: str
    path: str
    query: str = ""
    headers: tuple[tuple[str, str], ...] = ()
    read_body: Callable[[int], bytes] = no_body
    json_body: object = None

    def header_values(self, name: str) -> list[str]:
        return [value for key, value in self.headers if key == name]

    def header(self, name: str) -> str | None:
        values = self.header_values(name)
        return values[0] if values else None
