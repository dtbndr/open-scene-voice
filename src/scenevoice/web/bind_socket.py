import errno
import socket

from .port_busy_error import PortBusyError


def bind_socket(port: int) -> socket.socket:
    """Bind 127.0.0.1:port (port 0 picks a free one) and return the socket; the caller listens.

    SO_REUSEADDR lets a quick relaunch bind through TIME_WAIT. SO_REUSEPORT is never set: it would let a
    second listener share the port and hide a busy port.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))
    except OSError as error:
        sock.close()
        if error.errno != errno.EADDRINUSE:
            raise
        raise PortBusyError(
            f"Port {port} is already in use. Close the other SceneVoice window, or pass --port to use a different port."
        ) from error
    return sock
