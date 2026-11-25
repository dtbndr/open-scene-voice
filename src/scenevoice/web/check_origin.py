from .error_envelope import error_envelope
from .request import Request
from .response import Response


def check_origin(request: Request, port: int) -> Response | None:
    origin = request.header("origin")
    if origin is None and request.method in ("GET", "HEAD"):
        return None
    if origin != f"http://127.0.0.1:{port}":
        return error_envelope("bad_origin", "This request came from another site.")
    return None
