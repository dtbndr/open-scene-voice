import json
import socket
import threading
from collections.abc import Iterator

from keys_server_helper import running_keys_server
from keys_web_helper import NAME, STATUS_STDOUT, call, routes_over
from web_http_helper import parse_response
from web_stream_helper import ClosingChunks

from scenevoice.keys.key_names import KEY_NAMES
from scenevoice.web import (
    Request,
    StreamResponse,
    cookie_name,
    make_gate,
    make_server,
    make_token,
)

HEADERS = (("Content-Type", "text/event-stream"),)


def serve(routes: dict, token: str):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = make_server(sock, routes, make_gate(token, port), timeout=2)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    return server, thread, port


def stop(server, thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(5)


def open_request(port: int, token: str) -> socket.socket:
    client = socket.create_connection(("127.0.0.1", port), timeout=5)
    cookie = f"{cookie_name(port)}={token}"
    client.sendall(f"GET /api/live HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\nCookie: {cookie}\r\n\r\n".encode())
    return client


def test_a_stream_route_is_read_to_close_behind_the_cookie_with_no_length(loopback_only) -> None:
    token = make_token()
    chunks = ClosingChunks([b"a", b"b", b"c"])
    routes = {"/api/live": {"GET": lambda request: StreamResponse(200, HEADERS, chunks)}}
    server, thread, port = serve(routes, token)
    try:
        client = open_request(port, token)
        raw = b""
        while piece := client.recv(4096):
            raw += piece
        client.close()
        parsed = parse_response(raw)
        assert (parsed.status, parsed.body) == (200, b"abc")
        assert "content-length" not in parsed.headers
        assert parsed.one("Cache-Control") == "no-store"
        assert parsed.one("X-Frame-Options") == "DENY"
        assert chunks.closed
        stale = socket.create_connection(("127.0.0.1", port), timeout=5)
        stale.sendall(f"GET /api/live HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\n\r\n".encode())
        assert parse_response(stale.makefile("rb").read()).status == 401
        stale.close()
    finally:
        stop(server, thread)


def test_a_client_that_leaves_after_one_chunk_leaves_the_server_alive_quiet_and_the_generator_closed(
    loopback_only, capsys
) -> None:
    token = make_token()
    gone = threading.Event()
    closed = threading.Event()

    def many() -> Iterator[bytes]:
        try:
            yield b"first"
            gone.wait(5)
            for _ in range(300):
                yield b"x" * 4096
        finally:
            closed.set()

    def live(request: Request) -> StreamResponse:
        return StreamResponse(200, HEADERS, many())

    routes = {
        "/api/live": {"GET": live},
        "/api/ping": {"GET": lambda request: StreamResponse(200, HEADERS, iter([b"ok"]))},
    }
    server, thread, port = serve(routes, token)
    try:
        client = open_request(port, token)
        seen = b""
        while b"first" not in seen:
            seen += client.recv(4096)
        client.close()
        gone.set()
        assert closed.wait(5)
        again = open_request(port, token)
        raw = b""
        while piece := again.recv(4096):
            raw += piece
        again.close()
        assert parse_response(raw).status == 200
        captured = capsys.readouterr()
        assert (captured.out, captured.err) == ("", "")
    finally:
        stop(server, thread)


def test_head_on_a_stream_route_sends_the_head_only_and_never_starts_the_generator(loopback_only) -> None:
    token = make_token()
    chunks = ClosingChunks([b"a", b"b"])
    routes = {"/api/live": {"GET": lambda request: StreamResponse(200, HEADERS, chunks)}}
    server, thread, port = serve(routes, token)
    try:
        client = socket.create_connection(("127.0.0.1", port), timeout=5)
        cookie = f"{cookie_name(port)}={token}"
        client.sendall(f"HEAD /api/live HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\nCookie: {cookie}\r\n\r\n".encode())
        raw = b""
        while piece := client.recv(4096):
            raw += piece
        client.close()
        parsed = parse_response(raw)
        assert (parsed.status, parsed.body) == (200, b"")
        assert not chunks.started
        assert chunks.closed
    finally:
        stop(server, thread)


def test_keys_routes_are_registered_with_their_methods_and_need_the_cookie(loopback_only, stub_cli, tmp_path):
    stub = stub_cli(stdout=STATUS_STDOUT)
    with running_keys_server(stub, tmp_path) as server:
        assert parse_response(server.send("GET", "/api/keys", cookie=False)).json()["error"]["kind"] == "stale_link"
        assert parse_response(server.send("PUT", f"/api/keys/{NAME}", {"value": "a"}, cookie=False)).status == 401
        assert stub.calls() == []
        listing = parse_response(server.send("GET", "/api/keys"))
        assert (listing.status, listing.json()["suggested_region"]) == (200, "global")
        saved = parse_response(server.send("PUT", f"/api/keys/{NAME}", {"value": "a"}))
        assert (saved.status, saved.json()["path"]) == (200, "/k/keys.env")
        assert parse_response(server.send("DELETE", f"/api/keys/{NAME}")).status == 200
        wrong = parse_response(server.send("POST", "/api/keys", {}))
        assert (wrong.status, wrong.one("Allow")) == (405, "GET, HEAD")
        wrong_name = parse_response(server.send("GET", f"/api/keys/{NAME}"))
        assert (wrong_name.status, wrong_name.one("Allow")) == (405, "DELETE, PUT")
        assert parse_response(server.send("PUT", "/api/keys/NOPE", {"value": "a"})).status == 404


def test_the_child_environment_denylist_and_absolute_key_file_apply_through_the_keys_routes(stub_cli, tmp_path, monkeypatch):
    stub = stub_cli(stdout=STATUS_STDOUT)
    monkeypatch.chdir(tmp_path)
    environ = {**{name: "server-value" for name in KEY_NAMES}, "HOME": "/h", "SCENEVOICE_KEYS_FILE": "rel/keys.env"}
    routes = routes_over(stub, tmp_path, environ=environ)
    for method, path, body in (
        ("GET", "/api/keys", None),
        ("PUT", f"/api/keys/{NAME}", {"value": "a"}),
        ("DELETE", f"/api/keys/{NAME}", None),
    ):
        assert call(routes, method, path, body).status == 200
        recorded = stub.recording()
        assert all(recorded["env"][name] is None for name in KEY_NAMES)
        assert "server-value" not in recorded["env_values"]
        assert recorded["env"]["HOME"] == "/h"
        assert recorded["env"]["SCENEVOICE_KEYS_FILE"] == str(tmp_path / "rel" / "keys.env")
        assert recorded["cwd"] == str(tmp_path.resolve())
    assert len(stub.calls()) == 5
    assert json.loads(call(routes, "GET", "/api/keys").body)["path"]


CANARY = "canary-secret-VALUE-9f3a"


def test_the_submitted_value_appears_only_on_the_childs_stdin(loopback_only, stub_cli, capfd, tmp_path):
    stub = stub_cli(stdout=STATUS_STDOUT)
    with running_keys_server(stub, tmp_path) as server:
        ok = server.send("PUT", f"/api/keys/{NAME}", {"value": CANARY})
        stub = stub_cli(exit_code=1, stderr_lines=[f"scenevoice keys: FAIL refused {CANARY}"])
        refused = server.send("PUT", f"/api/keys/{NAME}", {"value": CANARY})
        stub = stub_cli(stdout="not json", by_verb={"set": {"stdout": ""}})
        unreadable = server.send("PUT", f"/api/keys/{NAME}", {"value": CANARY})
    assert b" 200 " in ok.split(b"\r\n")[0]
    assert b" 400 " in refused.split(b"\r\n")[0]
    assert b" 502 " in unreadable.split(b"\r\n")[0]
    for raw in (ok, refused, unreadable):
        assert CANARY.encode() not in raw
    out, err = capfd.readouterr()
    assert CANARY not in out + err
    calls = stub.calls()
    assert [c["argv"][1] for c in calls] == ["set", "status", "set", "set", "status"]
    assert all(c["stdin"] == CANARY.encode() for c in calls if c["argv"][1] == "set")
    for each in calls:
        assert CANARY not in json.dumps(each["argv"])
        assert CANARY not in each["env_values"]
        assert all(CANARY not in str(value) for value in each["env"].values())
