from .error_envelope import error_envelope
from .request import Request
from .response import Response


def check_host(request: Request, port: int) -> Response | None:
    if request.header("host") != f"127.0.0.1:{port}":
        return error_envelope("bad_host", "This address is not allowed.")
    return None
