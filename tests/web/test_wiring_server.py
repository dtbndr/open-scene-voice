import http.client
import inspect
import os
import queue
import signal
import socket
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer

import pytest
from web_http_helper import (
    PORT,
    SECURITY_HEADERS,
    make_request,
    parse_response,
    raw_exchange,
)

from scenevoice.keys.key_names import KEY_NAMES
from scenevoice.web import (
    Request,
    Response,
    build_allowlist,
    cookie_name,
    dispatch,
    ensure_index,
    make_gate,
    make_handler,
    make_server,
    make_token,
    serve_static,
)

ROUTES = {
    "/": {"GET": lambda request: Response(200, b"home")},
    "/api/keys": {"GET": lambda request: Response(200, b"keys")},
}


def start(token: str):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = make_server(sock, ROUTES, make_gate(token, port), timeout=0.3)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    return server, thread, port


def stop(server, thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(5)


def get(port: int, path: str, *extra: str, host: str | None = None) -> bytes:
    lines = [f"GET {path} HTTP/1.0", f"Host: {host or f'127.0.0.1:{port}'}", *extra]
    return raw_exchange(port, ("\r\n".join(lines) + "\r\n\r\n").encode())


def test_redeem_then_cookie_and_stale_links_through_the_real_server(loopback_only, capfd) -> None:
    token = make_token()
    first, first_thread, first_port = start(token)
    second, second_thread, second_port = start(make_token())
    try:
        stale_page = parse_response(get(first_port, "/"))
        stale_api = parse_response(get(first_port, "/api/keys"))
        assert (stale_page.status, stale_api.status) == (401, 401)
        assert b"scenevoice web" in stale_page.body
        assert stale_api.json()["error"]["kind"] == "stale_link"

        redeemed = parse_response(get(first_port, f"/?token={token}"))
        assert redeemed.status == 303
        assert redeemed.one("Location") == "/"
        assert redeemed.one("Content-Length") == "0"
        assert redeemed.one("Connection") == "close"
        set_cookie = redeemed.one("Set-Cookie")
        assert set_cookie == f"{cookie_name(first_port)}={token}; HttpOnly; SameSite=Lax; Path=/"

        cookie = set_cookie.split(";")[0]
        assert parse_response(get(first_port, "/", f"Cookie: {cookie}")).body == b"home"
        assert parse_response(get(first_port, "/api/keys", f"Cookie: {cookie}")).body == b"keys"
        # the other server has its own cookie name and its own token
        assert cookie_name(first_port) != cookie_name(second_port)
        assert parse_response(get(second_port, "/", f"Cookie: {cookie}")).status == 401
        # Host and Origin run before the gate
        bad_host = parse_response(get(first_port, "/", host="evil.test"))
        assert (bad_host.status, bad_host.json()["error"]["kind"]) == (403, "bad_host")
    finally:
        stop(first, first_thread)
        stop(second, second_thread)
    assert capfd.readouterr() == ("", "")


def test_the_real_server_end_to_end(loopback_only, capfd) -> None:
    gate_paths: list[str] = []

    def gate(request: Request) -> Response | None:
        gate_paths.append(request.path)
        return None

    routes = {"/api/ping": {"GET": lambda request: Response(200, b"pong")}}
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = make_server(sock, routes, gate, timeout=0.3)
    port = server.port
    host = f"127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        def get(path: str, host_header: str = host) -> bytes:
            return raw_exchange(port, f"GET {path} HTTP/1.0\r\nHost: {host_header}\r\n\r\n".encode())

        ok = parse_response(get("/api/ping?token=SECRETTOKEN"))
        missing = parse_response(get("/api/missing?token=SECRETTOKEN"))
        refused = parse_response(get("/api/ping", host_header="evil.test"))
        order = parse_response(
            raw_exchange(port, f"POST /api/ping HTTP/1.0\r\nHost: {host}\r\nHost: {host}\r\nOrigin: http://evil\r\n\r\n".encode())
        )
        assert [ok.status, missing.status, refused.status, order.status] == [200, 404, 403, 400]
        assert ok.body == b"pong"
        for parsed in (ok, missing, refused, order):
            assert parsed.headers["connection"] == ["close"]
            assert parsed.one("Content-Length") == str(len(parsed.body))
            assert {name: parsed.headers[name][0] for name in SECURITY_HEADERS} == SECURITY_HEADERS
        # duplicates, Host and Origin ran before the gate; the gate ran before route lookup
        assert gate_paths == ["/api/ping", "/api/missing"]
        # an idle connection is closed by the socket timeout
        assert raw_exchange(port, b"") == b""
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
    assert capfd.readouterr() == ("", "")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def read_link(process: subprocess.Popen, seconds: float = 30.0) -> str:
    lines: queue.Queue[str] = queue.Queue()
    threading.Thread(target=lambda: [lines.put(line) for line in process.stdout], daemon=True).start()
    while True:
        line = lines.get(timeout=seconds)  # raises queue.Empty on a hang instead of blocking
        if line.startswith("Open it here: "):
            return line.split(": ", 1)[1].strip()


def get_web_wiring(port: int, path: str, cookie: str | None = None) -> http.client.HTTPResponse:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    connection.request("GET", path, headers={"Cookie": cookie} if cookie else {})
    return connection.getresponse()


def test_web_serves_its_link_and_keys_api_then_exits_zero_on_sigint(tmp_path):
    home, scratch = tmp_path / "home", tmp_path / "tmpdir"
    home.mkdir()
    scratch.mkdir()
    env = {k: v for k, v in os.environ.items() if k not in KEY_NAMES}
    env |= {"HOME": str(home), "SCENEVOICE_KEYS_FILE": str(home / "keys.env"), "TMPDIR": str(scratch)}
    port = free_port()
    command = [sys.executable, "-B", "-m", "scenevoice", "web", "--no-open", "--port", str(port)]
    process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, text=True, stdin=subprocess.DEVNULL)
    try:
        link = read_link(process)
        assert link.startswith(f"http://127.0.0.1:{port}/?token=")
        redeemed = get_web_wiring(port, link.removeprefix(f"http://127.0.0.1:{port}"))
        assert redeemed.status == 303
        cookie = redeemed.getheader("Set-Cookie", "").split(";")[0]
        assert cookie.startswith(f"scenevoice_{port}=")
        assert get_web_wiring(port, "/api/keys", cookie).status == 200
        page = get_web_wiring(port, "/", cookie)
        assert page.status == 200 and b"<html" in page.read().lower()  # an index page (build or placeholder), not the stale-link page
        process.send_signal(signal.SIGINT)
        assert process.wait(timeout=15) == 0
        assert list(scratch.iterdir()) == []
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()


TOKEN = "t" * 20


def dispatch_real(request):
    allowlist = ensure_index({})  # the built-in placeholder: the same with or without a UI build
    return dispatch(request, {}, make_gate(TOKEN, PORT), PORT, lambda r: serve_static(r, allowlist))


def test_the_built_in_placeholder_is_script_free_and_served_only_with_the_cookie() -> None:
    allowlist = ensure_index({})
    assert b"<script" not in allowlist["index.html"].lower()
    host = ("host", f"127.0.0.1:{PORT}")
    cookie = ("cookie", f"{cookie_name(PORT)}={TOKEN}")
    served = dispatch_real(make_request("GET", "/", [host, cookie]))
    assert (served.status, served.body) == (200, allowlist["index.html"])
    stale = dispatch_real(make_request("GET", "/", [host]))
    assert stale.status == 401
    assert stale.body != allowlist["index.html"]
    assert dispatch_real(make_request("GET", "/%61pi/keys", [host, cookie])).status == 404


def test_the_real_server_serves_static_after_the_gate(loopback_only) -> None:
    token = make_token()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    allowlist = ensure_index(build_allowlist())
    server = make_server(sock, {}, make_gate(token, port), timeout=0.3, static=lambda r: serve_static(r, allowlist))
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        cookie = f"Cookie: {cookie_name(port)}={token}"

        def get(method: str, *extra: str) -> bytes:
            lines = [f"{method} /projects/1 HTTP/1.0", f"Host: 127.0.0.1:{port}", *extra]
            return raw_exchange(port, ("\r\n".join(lines) + "\r\n\r\n").encode())

        assert parse_response(get("GET")).status == 401
        page = parse_response(get("GET", cookie))
        assert (page.status, page.body) == (200, allowlist["index.html"])
        head = parse_response(get("HEAD", cookie))
        assert (head.one("Content-Length"), head.body) == (str(len(allowlist["index.html"])), b"")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


@pytest.mark.parametrize("factory", [make_server, make_handler])
def test_the_gate_is_a_required_parameter(factory) -> None:
    parameter = inspect.signature(factory).parameters["gate"]
    assert parameter.default is inspect.Parameter.empty


@pytest.fixture
def bound(loopback_only) -> socket.socket:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    yield sock
    sock.close()


def test_the_server_adopts_the_bound_socket_without_resolving_a_hostname(bound, monkeypatch) -> None:
    def no_getfqdn(*args, **kwargs):
        raise AssertionError("server_bind was used")

    monkeypatch.setattr(socket, "getfqdn", no_getfqdn)
    server = make_server(bound, {}, lambda request: None, timeout=1.5)
    try:
        assert isinstance(server, ThreadingHTTPServer)
        assert server.socket is bound
        assert server.port == bound.getsockname()[1]
        assert server.daemon_threads is True
        assert server.RequestHandlerClass.timeout == 1.5
    finally:
        server.server_close()


def test_an_unexpected_handler_error_prints_nothing(bound, capfd) -> None:
    server = make_server(bound, {}, lambda request: None)
    try:
        try:
            raise RuntimeError("detail")
        except RuntimeError:
            server.handle_error(None, ("127.0.0.1", 1))
    finally:
        server.server_close()
    assert capfd.readouterr() == ("", "")
