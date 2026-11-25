"""A real loopback server over the three job routes and a real runner driving the stub CLI, plus an SSE client."""

import json
import socket
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from job_events_helper import parse_sse
from job_runner_helper import make_runner, start_job
from keys_server_helper import Running
from web_http_helper import ParsedResponse, parse_response

from scenevoice.web import (
    JobEvents,
    JobRunner,
    JobSpec,
    cookie_name,
    make_gate,
    make_server,
    make_token,
    register_job_routes,
)


class JobsServer(Running):
    def __init__(self, port: int, token: str, runner: JobRunner, hub: JobEvents) -> None:
        super().__init__(port, token)
        self.runner = runner
        self.hub = hub

    def start(self, scrub: Callable[[str], str] = lambda text: text, **fields: Any) -> JobSpec:
        observer = self.hub.observer(scrub=scrub, on_scene_done=self.runner.note_scene_done)
        return start_job(self.runner, observer=observer, **fields)

    def open_events(self, last_event_id: str | None = None) -> socket.socket:
        client = socket.create_connection(("127.0.0.1", self.port), timeout=15)
        lines = [
            "GET /api/jobs/current/events HTTP/1.0",
            f"Host: 127.0.0.1:{self.port}",
            f"Cookie: {cookie_name(self.port)}={self.token}",
        ]
        if last_event_id is not None:
            lines.append(f"Last-Event-ID: {last_event_id}")
        client.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
        return client

    def read_until(self, client: socket.socket, marker: bytes) -> bytes:
        seen = b""
        while marker not in seen:
            piece = client.recv(4096)
            assert piece, "the stream closed before the marker arrived"
            seen += piece
        return seen

    def read_to_close(self, client: socket.socket, seen: bytes = b"") -> ParsedResponse:
        while piece := client.recv(4096):
            seen += piece
        client.close()
        return parse_response(seen)

    def stream(self, last_event_id: str | None = None) -> tuple[ParsedResponse, list[tuple[str, dict[str, Any]]]]:
        parsed = self.read_to_close(self.open_events(last_event_id))
        return parsed, parse_sse(parsed.body)

    def current(self) -> dict[str, Any]:
        return json.loads(parse_response(self.send("GET", "/api/jobs/current")).body)


@contextmanager
def running_jobs_server(stub: Any, tmp_path: Path, **runner_options: Any) -> Iterator[JobsServer]:
    runner = make_runner(stub, tmp_path, **runner_options)
    hub = JobEvents()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    token = make_token()
    server = make_server(sock, register_job_routes(runner, hub, keepalive=0.2), make_gate(token, port), timeout=5.0)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield JobsServer(port, token, runner, hub)
    finally:
        runner.shutdown()
        hub.close()
        server.shutdown()
        server.server_close()
        thread.join(5)
