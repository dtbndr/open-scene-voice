from urllib.parse import unquote

from .content_type import content_type
from .error_envelope import error_envelope
from .request import Request
from .response import Response


def serve_static(request: Request, allowlist: dict[str, bytes]) -> Response:
    """Look the decoded path up in the precomputed set; it is never joined onto a filesystem path."""
    decoded = unquote(request.path)
    lowered = decoded.lower()
    if lowered == "/api" or lowered.startswith("/api/") or not decoded.startswith("/"):
        return error_envelope("not_found", "Nothing is here.")
    name = "index.html" if decoded == "/" else decoded[1:]
    if name not in allowlist and "." not in name.rsplit("/", 1)[-1]:
        name = "index.html"  # single-page-app fallback: only extensionless paths
    kind = content_type(name)
    if name not in allowlist or kind is None:
        return error_envelope("not_found", "Nothing is here.")
    if request.method not in ("GET", "HEAD"):
        return error_envelope("method_not_allowed", "That method is not allowed here.", headers=(("Allow", "GET, HEAD"),))
    return Response(200, allowlist[name], (("Content-Type", kind),))
