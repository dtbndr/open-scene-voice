from dataclasses import replace

from .check_duplicates import check_duplicates
from .check_host import check_host
from .check_origin import check_origin
from .error_envelope import error_envelope
from .read_json_body import read_json_body
from .request import Request
from .response import Response
from .route_table import Gate, Handler, RouteTable
from .stream_response import StreamResponse


def run_checks(
    request: Request, routes: RouteTable, gate: Gate, port: int, static: Handler | None
) -> Response | StreamResponse:
    refusal = (
        check_duplicates(request)
        or check_host(request, port)
        or check_origin(request, port)
        or gate(request)
    )
    if refusal is not None:
        return refusal
    methods = routes.get(request.path)
    if methods is None:
        if static is not None:
            return static(request)
        return error_envelope("not_found", "Nothing is here.")
    handler = methods.get("GET" if request.method == "HEAD" else request.method)
    if handler is None:
        allowed = {*methods, "HEAD"} if "GET" in methods else set(methods)
        allow = ("Allow", ", ".join(sorted(allowed)))
        return error_envelope("method_not_allowed", "That method is not allowed here.", headers=(allow,))
    body = read_json_body(request)
    if isinstance(body, Response):
        return body
    return handler(replace(request, json_body=body.value))


def dispatch(
    request: Request, routes: RouteTable, gate: Gate, port: int, static: Handler | None = None
) -> Response | StreamResponse:
    """Every request, whatever the method, goes through here: duplicates, Host, Origin, gate, route, static, body."""
    try:
        return run_checks(request, routes, gate, port, static)
    except Exception:
        return error_envelope("internal_error", "Something went wrong.")
