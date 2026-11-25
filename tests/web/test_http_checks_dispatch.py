import json
from io import BytesIO

import pytest
from web_http_helper import HOST, ORIGIN, PORT, make_request, parse_response

from scenevoice.web import (
    Request,
    Response,
    StreamResponse,
    dispatch,
    serve_static,
    write_response,
)

JSON_HEADERS = [("content-type", "application/json")]


def ok(request: Request) -> Response:
    return Response(200, b"ok")


def echo_json(request: Request) -> Response:
    return Response(200, json.dumps(request.json_body).encode())


def boom(request: Request) -> Response:
    raise RuntimeError("secret-looking detail")


def routes() -> dict:
    return {"/api/ping": {"GET": ok, "DELETE": ok}, "/api/echo": {"POST": echo_json}, "/api/boom": {"GET": boom}}


def refuse(request: Request) -> Response:
    return Response(418)


def allow(request: Request) -> Response | None:
    return None


def run(request: Request, gate=allow) -> Response:
    return dispatch(request, routes(), gate, PORT)


def kind(response: Response) -> str:
    return json.loads(response.body)["error"]["kind"]


def test_a_known_path_reaches_its_handler_and_head_is_routed_like_get() -> None:
    assert run(make_request("GET")).body == b"ok"
    assert run(make_request("HEAD")).body == b"ok"


def test_a_post_handler_receives_the_parsed_json() -> None:
    headers = [("host", HOST), ("origin", ORIGIN), *JSON_HEADERS, ("content-length", "7")]
    assert run(make_request("POST", "/api/echo", headers, b'{"a":1}')).body == b'{"a": 1}'


@pytest.mark.parametrize("path", ["/api/nope", "/nope", "/%61pi/ping", "/api/ping/", "/api/ping?x"])
def test_an_unknown_path_is_404_never_a_fallback(path: str) -> None:
    response = run(make_request("GET", path))
    assert (response.status, kind(response)) == (404, "not_found")


def test_a_wrong_method_is_405_with_allow_and_options_is_405() -> None:
    for method in ("POST", "OPTIONS"):
        headers = [("host", HOST), ("origin", ORIGIN)]
        response = run(make_request(method, "/api/ping", headers))
        assert (response.status, kind(response)) == (405, "method_not_allowed")
        assert ("Allow", "DELETE, GET, HEAD") in response.headers


def test_a_handler_exception_is_a_fixed_500() -> None:
    response = run(make_request("GET", "/api/boom"))
    assert (response.status, kind(response)) == (500, "internal_error")
    assert b"secret-looking" not in response.body


def test_the_gate_response_is_returned_as_is_and_sees_the_request() -> None:
    seen: list[Request] = []
    stale = Response(401, b"stale")

    def gate(request: Request) -> Response | None:
        seen.append(request)
        return stale

    request = make_request("GET")
    assert run(request, gate) is stale
    assert seen == [request]


@pytest.mark.parametrize(
    ("headers", "method", "path", "status", "expected_kind"),
    [
        # every later check would also fail; the earliest one wins
        ([("host", "evil"), ("host", "evil"), ("origin", "http://evil")], "POST", "/nope", 400, "bad_request"),
        ([("host", "evil"), ("origin", "http://evil")], "POST", "/nope", 403, "bad_host"),
        ([("host", HOST), ("origin", "http://evil")], "POST", "/nope", 403, "bad_origin"),
        ([("host", HOST), ("origin", ORIGIN)], "POST", "/nope", 418, None),
    ],
)
def test_checks_run_in_order_duplicates_host_origin_gate(headers, method, path, status, expected_kind) -> None:
    response = run(make_request(method, path, headers), gate=refuse)
    assert response.status == status
    if expected_kind:
        assert kind(response) == expected_kind


def test_route_lookup_runs_after_the_gate_and_the_body_check_after_the_route() -> None:
    headers = [("host", HOST), ("origin", ORIGIN), ("content-type", "text/plain"), ("content-length", "2")]
    assert run(make_request("POST", "/nope", headers)).status == 404
    assert run(make_request("POST", "/api/echo", headers)).status == 415


def test_a_stream_response_comes_back_unchanged_and_an_early_exception_is_still_internal_error() -> None:
    stream = StreamResponse(200, (("Content-Type", "text/event-stream"),), iter([b"x"]))
    routes = {"/api/live": {"GET": lambda request: stream}, "/api/dead": {"GET": boom}}
    assert dispatch(make_request("GET", "/api/live"), routes, allow, PORT) is stream
    failed = dispatch(make_request("GET", "/api/dead"), routes, allow, PORT)
    assert isinstance(failed, Response)
    assert (failed.status, kind(failed)) == (500, "internal_error")


ALLOWLIST = {"index.html": b"<p>home</p>", "_app/a.js": b"let a", "x.pyc": b"bytecode", "note.txt": b"hi"}


def serve(path: str, method: str = "GET", allowlist: dict | None = None) -> Response:
    return serve_static(make_request(method, path), ALLOWLIST if allowlist is None else allowlist)


def kind_serve_static(response: Response) -> str:
    return json.loads(response.body)["error"]["kind"]


def test_root_is_index_html() -> None:
    response = serve("/")
    assert (response.status, response.body) == (200, b"<p>home</p>")
    assert ("Content-Type", "text/html; charset=utf-8") in response.headers
    assert response.no_store is False


def test_a_listed_path_gives_its_bytes_and_type() -> None:
    response = serve("/_app/a.js")
    assert (response.status, response.body) == (200, b"let a")
    assert ("Content-Type", "text/javascript; charset=utf-8") in response.headers


def test_an_unknown_extensionless_path_is_the_spa_fallback() -> None:
    response = serve("/projects/3")
    assert (response.status, response.body) == (200, b"<p>home</p>")
    assert ("Content-Type", "text/html; charset=utf-8") in response.headers


def test_an_unknown_path_with_an_extension_is_404() -> None:
    response = serve("/missing.js")
    assert (response.status, kind_serve_static(response)) == (404, "not_found")


def test_a_listed_file_with_an_unmapped_extension_is_not_served() -> None:
    assert serve("/x.pyc").status == 404


@pytest.mark.parametrize("path", ["/api/keys", "/api", "/API/keys", "/%61pi/keys", "/api%2Fkeys", "/%61pi"])
def test_an_api_path_never_falls_back(path: str) -> None:
    response = serve(path)
    assert (response.status, kind_serve_static(response)) == (404, "not_found")


@pytest.mark.parametrize("path", ["/..%2f..%2fetc/passwd", "/%2e%2e/", "//", "/a%00b"])
def test_odd_extensionless_paths_are_looked_up_not_joined_and_fall_back(path: str) -> None:
    response = serve(path)
    assert (response.status, response.body) == (200, b"<p>home</p>")


@pytest.mark.parametrize("path", ["/../index.html", "/%2e%2e%2f%2e%2e%2findex.html", "/\\..\\x", "/a%00.js"])
def test_odd_paths_with_an_extension_are_404(path: str) -> None:
    assert serve(path).status == 404


def test_an_encoded_path_to_an_entry_is_found_but_a_traversal_is_not() -> None:
    assert serve("/%5Fapp/a.js").body == b"let a"
    assert serve("/_app/%2e%2e/index.html").status == 404


def test_percent_decoding_happens_once() -> None:
    allowlist = {"index.html": b"home", "a.b": b"x"}
    assert serve("/a%252eb", allowlist=allowlist).body == b"home"  # decodes to "a%2eb": no extension, no entry
    assert serve("/a%2eb.txt", allowlist={**allowlist, "a.b.txt": b"y"}).body == b"y"
    assert serve("/a%252eb.txt", allowlist={**allowlist, "a.b.txt": b"y"}).status == 404


def test_head_has_the_get_length_and_no_body() -> None:
    get, head = serve("/_app/a.js"), serve("/_app/a.js", "HEAD")
    assert head == get
    out = BytesIO()
    write_response(out, head, head_only=True)
    parsed = parse_response(out.getvalue())
    assert (parsed.status, parsed.one("Content-Length"), parsed.body) == (200, str(len(b"let a")), b"")


def test_a_non_get_method_on_a_static_path_is_405_with_allow() -> None:
    for path in ("/", "/_app/a.js", "/projects/3"):
        response = serve(path, "POST")
        assert (response.status, kind_serve_static(response)) == (405, "method_not_allowed")
        assert ("Allow", "GET, HEAD") in response.headers


def test_a_non_get_method_on_a_missing_file_or_api_path_is_404() -> None:
    assert serve("/missing.js", "POST").status == 404
    assert serve("/api/x", "POST").status == 404
