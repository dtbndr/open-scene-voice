from .error_envelope import error_envelope
from .request import Request
from .response import Response

MESSAGE = (
    "This link is from an earlier run of SceneVoice. Open Terminal, type scenevoice web "
    "and press Return. A new window opens with your projects."
)
PAGE = (
    "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
    "<title>SceneVoice</title>\n</head>\n<body>\n"
    f"<main><h1>SceneVoice</h1><p>{MESSAGE}</p></main>\n</body>\n</html>\n"
)


def stale_response(request: Request) -> Response:
    """401 for a request without a valid cookie: JSON under /api/, an inline page (built here, no file) elsewhere."""
    if request.path.startswith("/api/"):
        return error_envelope("stale_link", MESSAGE)
    return Response(401, PAGE.encode("utf-8"), (("Content-Type", "text/html; charset=utf-8"),), no_store=True)
