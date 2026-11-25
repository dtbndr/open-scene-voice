from .error_envelope import error_envelope
from .request import Request
from .response import Response

GUARDED = ("host", "origin", "content-type", "content-length")


def check_duplicates(request: Request) -> Response | None:
    for name in GUARDED:
        if len(request.header_values(name)) > 1:
            return error_envelope("bad_request", "The request repeats a header that must appear once.")
    return None
