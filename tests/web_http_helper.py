"""Shared helpers for the web request tests: request builders, a fake connection and a response parser."""

import json
import socket
from dataclasses import dataclass
from io import BytesIO
from types import SimpleNamespace
from typing import Any

from scenevoice.web import Request

PORT = 5000
HOST = f"127.0.0.1:{PORT}"
ORIGIN = f"http://127.0.0.1:{PORT}"
SECURITY_HEADERS = {
    "referrer-policy": "no-referrer",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "content-security-policy": "frame-ancestors 'none'",
}


def make_request(
    method: str = "GET",
    path: str = "/api/ping",
    headers: list[tuple[str, str]] | None = None,
    body: bytes = b"",
) -> Request:
    """Build a Request; `headers=None` means a correct Host only, a list replaces every header."""
    pairs = [("host", HOST)] if headers is None else headers
    return Request(method=method, path=path, headers=tuple(pairs), read_body=BytesIO(body).read)


@dataclass(frozen=True)
class ParsedResponse:
    status: int
    version: str
    headers: dict[str, list[str]]
    body: bytes

    def one(self, name: str) -> str:
        return self.headers[name.lower()][0]

    def json(self) -> Any:
        return json.loads(self.body)


def parse_response(raw: bytes) -> ParsedResponse:
    head, _, body = raw.partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    version, status, *_ = lines[0].split(" ", 2)
    headers: dict[str, list[str]] = {}
    for line in lines[1:]:
        name, _, value = line.partition(":")
        headers.setdefault(name.lower(), []).append(value.strip())
    return ParsedResponse(int(status), version, headers, body)


class FakeSocket:
    """Just enough socket for a StreamRequestHandler: reads canned bytes, records what is sent."""

    def __init__(self, incoming: bytes) -> None:
        self._incoming = BytesIO(incoming)
        self.sent = bytearray()

    def makefile(self, mode: str, bufsize: int = -1) -> BytesIO:
        return self._incoming

    def settimeout(self, value: float | None) -> None:
        self.timeout = value

    def sendall(self, data: Any) -> None:
        self.sent += data

    def close(self) -> None:
        pass


def run_handler(handler_class: type, incoming: bytes) -> bytes:
    """Run one connection through the handler class without a real socket; return the bytes it wrote."""
    sock = FakeSocket(incoming)
    server = SimpleNamespace(server_address=("127.0.0.1", PORT), port=PORT)
    handler_class(sock, ("127.0.0.1", 1), server)
    return bytes(sock.sent)


def raw_exchange(port: int, payload: bytes) -> bytes:
    """Send raw bytes to 127.0.0.1:port and read until the server closes the connection."""
    with socket.create_connection(("127.0.0.1", port), timeout=5) as conn:
        conn.sendall(payload)
        chunks = []
        while chunk := conn.recv(4096):
            chunks.append(chunk)
    return b"".join(chunks)
