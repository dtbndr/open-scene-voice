from http.server import BaseHTTPRequestHandler
from typing import Any, cast

from .dispatch import dispatch
from .error_envelope import error_envelope
from .quiet_server import QuietServer
from .request import Request
from .route_table import Gate, RouteTable
from .route_table import Handler as RouteHandler
from .stream_response import StreamResponse
from .write_response import write_response
from .write_stream import write_stream


def make_handler(
    routes: RouteTable, gate: Gate, timeout: float = 30.0, static: RouteHandler | None = None
) -> type[BaseHTTPRequestHandler]:
    """Build the handler class; `gate` is required on purpose. Only this class writes, only via write_response."""

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def _serve(self) -> None:
            path, _, query = self.path.partition("?")
            headers = tuple((name.lower(), value) for name, value in self.headers.items())
            request = Request(self.command, path, query, headers, self.rfile.read)
            port = cast(QuietServer, self.server).port
            response = dispatch(request, routes, gate, port, static)
            head_only = self.command == "HEAD"
            if isinstance(response, StreamResponse):
                write_stream(self.wfile, response, head_only=head_only)
            else:
                write_response(self.wfile, response, head_only=head_only)

        def __getattr__(self, name: str) -> Any:
            if name.startswith("do_"):
                return self._serve
            raise AttributeError(name)

        def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
            response = error_envelope("bad_request", "The request could not be understood.", status=code)
            write_response(self.wfile, response, head_only=self.command == "HEAD")

        def log_message(self, format: str, *args: Any) -> None:
            return None

        def log_request(self, code: Any = "-", size: Any = "-") -> None:
            return None

        def log_error(self, format: str, *args: Any) -> None:
            return None

    Handler.timeout = timeout
    return Handler
