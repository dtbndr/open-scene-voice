from .quiet_server import QuietServer


def serve_until_stopped(server: QuietServer) -> None:
    """Block serving requests until the process is interrupted."""
    server.serve_forever()
