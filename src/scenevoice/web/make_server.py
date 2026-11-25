import socket

from .make_handler import make_handler
from .quiet_server import QuietServer
from .route_table import Gate, Handler, RouteTable


def make_server(
    bound_socket: socket.socket, routes: RouteTable, gate: Gate, timeout: float = 30.0, static: Handler | None = None
) -> QuietServer:
    """Serve on an already-bound socket (the caller binds). `gate` is required: nothing here allows all."""
    server = QuietServer(("127.0.0.1", 0), make_handler(routes, gate, timeout, static), bind_and_activate=False)
    server.socket.close()
    server.socket = bound_socket
    server.server_address = bound_socket.getsockname()
    server.server_activate()
    return server
