import json

from .response import Response

KIND_STATUS = {
    "stale_link": 401,
    "bad_host": 403,
    "bad_origin": 403,
    "not_found": 404,
    "method_not_allowed": 405,
    "bad_request": 400,
    "cli_failed": 502,
    "unsupported": 501,
    "internal_error": 500,
    "busy": 409,
    "changed": 409,
    "not_allowed": 409,
}


def error_envelope(
    kind: str, message: str, *, status: int | None = None, headers: tuple[tuple[str, str], ...] = ()
) -> Response:
    """The one JSON error shape; `status` overrides only where a kind spans several (bad_request: 400, 413, 415)."""
    if kind not in KIND_STATUS:
        raise ValueError(f"unknown error kind: {kind}")
    body = json.dumps({"error": {"kind": kind, "message": message}}).encode("utf-8")
    return Response(
        status or KIND_STATUS[kind],
        body,
        (("Content-Type", "application/json; charset=utf-8"), *headers),
        no_store=True,
    )
