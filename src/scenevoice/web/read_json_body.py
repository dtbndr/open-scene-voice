import json

from .error_envelope import error_envelope
from .json_body import JsonBody
from .request import Request
from .response import Response

BODY_CAP = 64 * 1024
BODYLESS = ("GET", "HEAD", "DELETE")


def bad(message: str, status: int = 400) -> Response:
    return error_envelope("bad_request", message, status=status)


def has_lone_surrogate(value: object) -> bool:
    """Scan with an explicit stack: nesting depth must never reach the interpreter's recursion limit."""
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            try:
                item.encode("utf-8")
            except UnicodeEncodeError:
                return True
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, dict):
            stack.extend(item.keys())
            stack.extend(item.values())
    return False


def read_json_body(request: Request) -> JsonBody | Response:
    """Framing and JSON rules for one request body; the cap is decided from Content-Length before any read."""
    if request.header("transfer-encoding") is not None:
        return bad("This request uses an unsupported transfer encoding.")
    length = request.header("content-length")
    bodyless = request.method in BODYLESS
    if length is None and bodyless:
        return JsonBody(None)
    if length is None or not (length.isascii() and length.isdigit()):
        return bad("The request needs a valid Content-Length.")
    digits = length.lstrip("0") or "0"
    if bodyless:
        return JsonBody(None) if digits == "0" else bad("This request must not have a body.")
    media_type = (request.header("content-type") or "").split(";")[0].strip().lower()
    if media_type != "application/json":
        return bad("The request body must be JSON.", status=415)
    if len(digits) > 9 or int(digits) > BODY_CAP:
        return bad("The request body is too large.", status=413)
    count = int(digits)
    try:
        raw = request.read_body(count)
    except OSError:
        return bad("The request body could not be read.")
    if len(raw) != count:
        return bad("The request body is shorter than its Content-Length.")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError):
        return bad("The request body is not valid JSON.")
    if has_lone_surrogate(value):
        return bad("The request body is not valid JSON.")
    return JsonBody(value)
