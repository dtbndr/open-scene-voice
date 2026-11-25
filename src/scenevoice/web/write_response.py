from io import BufferedIOBase

from .build_head import build_head
from .response import Response


def write_response(wfile: BufferedIOBase, response: Response, head_only: bool = False) -> None:
    """The one finite-response writer: exact Content-Length, Connection: close, security headers."""
    wfile.write(build_head(response.status, response.headers, response.no_store, len(response.body)))
    if not head_only:
        wfile.write(response.body)
    wfile.flush()
