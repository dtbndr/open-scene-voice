import json

from .response import Response


def json_response(status: int, value: object) -> Response:
    """A JSON answer that is never cached; the body is whole-document `json.dumps`."""
    body = json.dumps(value, ensure_ascii=False).encode("utf-8")
    return Response(status, body, (("Content-Type", "application/json; charset=utf-8"),), no_store=True)
