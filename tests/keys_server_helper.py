"""A real loopback server over the keys routes, for the wiring and redaction tests."""

import json
import socket
import threading
from contextlib import contextmanager
from typing import Any

from keys_web_helper import routes_over
from web_http_helper import raw_exchange

from scenevoice.web import cookie_name, make_gate, make_server, make_token


class Running:
    def __init__(self, port: int, token: str) -> None:
        self.port = port
        self.token = token

    def send(self, method: str, path: str, body: object = None, cookie: bool = True) -> bytes:
        payload = b"" if body is None else json.dumps(body).encode()
        lines = [f"{method} {path} HTTP/1.0", f"Host: 127.0.0.1:{self.port}", f"Origin: http://127.0.0.1:{self.port}"]
        if cookie:
            lines.append(f"Cookie: {cookie_name(self.port)}={self.token}")
        if body is not None:
            lines += ["Content-Type: application/json", f"Content-Length: {len(payload)}"]
        return raw_exchange(self.port, ("\r\n".join(lines) + "\r\n\r\n").encode() + payload)


@contextmanager
def running_keys_server(stub: Any, cwd: Any, **options: Any):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    token = make_token()
    server = make_server(sock, routes_over(stub, cwd, **options), make_gate(token, port), timeout=2.0)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield Running(port, token)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
