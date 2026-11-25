from http.server import ThreadingHTTPServer
from typing import Any


class QuietServer(ThreadingHTTPServer):
    """Threaded server that adopts a bound socket, exits with Control-C and prints nothing, ever."""

    daemon_threads = True

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    def handle_error(self, request: Any, client_address: Any) -> None:
        return None
