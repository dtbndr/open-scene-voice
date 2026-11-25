import io
import json
import os
import socket
import threading
import zipfile
from contextlib import contextmanager

from keys_server_helper import Running
from keys_web_helper import STATUS_STDOUT, routes_over
from project_routes_helper import make_project_routes
from web_http_helper import parse_response, raw_exchange

from scenevoice.web import (
    bind_runner,
    chain_routes,
    cookie_name,
    make_gate,
    make_root_getter,
    make_server,
    make_token,
)


@contextmanager
def running(stub, tmp_path, workspace, key_file=None, **options):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    token = make_token()
    projects = make_project_routes(root_getter=make_root_getter(workspace, key_file), key_file=key_file, **options)
    routes = chain_routes(routes_over(stub, tmp_path), projects)
    server = make_server(sock, routes, make_gate(token, port), timeout=2.0)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield Running(port, token)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_the_project_routes_sit_behind_the_gate_and_the_origin_rule_beside_the_keys_routes(loopback_only, stub_cli, tmp_path):
    stub = stub_cli(stdout=STATUS_STDOUT)
    with running(stub, tmp_path, tmp_path / "ws") as server:
        assert parse_response(server.send("GET", "/api/projects", cookie=False)).json()["error"]["kind"] == "stale_link"
        created = parse_response(server.send("POST", "/api/projects", {"name": "My Video"}))
        assert (created.status, created.json()) == (201, {"id": "my-video"})
        listing = parse_response(server.send("GET", "/api/projects")).json()
        assert [entry["id"] for entry in listing["projects"]] == ["my-video"]
        body = json.dumps({"name": "x"}).encode()
        no_origin = (
            f"POST /api/projects HTTP/1.0\r\nHost: 127.0.0.1:{server.port}\r\n"
            f"Cookie: {cookie_name(server.port)}={server.token}\r\n"
            f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n"
        ).encode() + body
        refused = parse_response(raw_exchange(server.port, no_origin))
        assert (refused.status, refused.json()["error"]["kind"]) == (403, "bad_origin")
        assert parse_response(server.send("GET", "/api/keys")).status == 200  # the chain did not break the keys routes


def test_a_workspace_symlinked_onto_the_key_file_folder_answers_a_400_bad_request(loopback_only, stub_cli, tmp_path):
    keys = tmp_path / "keys"
    keys.mkdir()
    key_file = keys / "keys.env"
    key_file.write_text("x")
    workspace = tmp_path / "ws"
    workspace.symlink_to(keys)
    with running(stub_cli(stdout=STATUS_STDOUT), tmp_path, workspace, key_file) as server:
        for method, body in (("GET", None), ("POST", {"name": "x"})):
            answer = parse_response(server.send(method, "/api/projects", body))
            assert (answer.status, answer.json()["error"]["kind"]) == (400, "bad_request")


def test_a_saved_script_reads_back_the_same_text_through_the_server(loopback_only, stub_cli, tmp_path):
    text = "﻿One\r\nTwo no newline"
    with running(stub_cli(stdout=STATUS_STDOUT), tmp_path, tmp_path / "ws") as server:
        server.send("POST", "/api/projects", {"name": "My Video"})
        assert parse_response(server.send("GET", "/api/projects/my-video/script")).json() == {"text": ""}
        saved = parse_response(server.send("PUT", "/api/projects/my-video/script", {"text": text}))
        assert (saved.status, saved.json()) == (200, {"saved": True})
        assert parse_response(server.send("GET", "/api/projects/my-video/script")).json() == {"text": text}


def test_a_check_through_the_server_answers_the_plan_result_and_leaves_nothing_behind(loopback_only, stub_cli, tmp_path):
    plan = json.dumps({"scenes": [{"title": "a"}, {"title": "b"}, {"title": "c"}]})
    stub = stub_cli(stdout=plan, stderr_lines=[json.dumps({"command": "plan", "event": "ok", "message": "OK {path}"})])
    launch = tmp_path / "launch"
    launch.mkdir()
    options = {"run": bind_runner(launch, {"HOME": "/h"}, stub.prefix), "launch_dir": launch}
    with running(stub, tmp_path, tmp_path / "ws", **options) as server:
        server.send("POST", "/api/projects", {"name": "My Video"})
        answer = parse_response(server.send("POST", "/api/projects/my-video/check", {"text": "x"}))
        assert (answer.status, answer.json()) == (200, {"ok": True, "scenes": 3})
    assert stub.recording()["argv"][:3] == ["plan", "--progress", "json"]  # positive control: the stub answered
    assert os.listdir(launch) == []


def test_the_project_detail_through_the_server_reads_the_disk_runs_plan_once_and_leaves_nothing_behind(loopback_only, stub_cli, tmp_path):
    plan = json.dumps({"scenes": [{"ordinal": 1, "title": "a", "body": "Hello"}, {"ordinal": 2, "title": "b", "body": "W\u00f6rld!"}]})
    stub = stub_cli(stdout=plan, stderr_lines=[json.dumps({"command": "plan", "event": "ok", "message": "OK {path}"})])
    launch = tmp_path / "launch"
    launch.mkdir()
    options = {"run": bind_runner(launch, {"HOME": "/h"}, stub.prefix), "launch_dir": launch}
    with running(stub, tmp_path, tmp_path / "ws", **options) as server:
        assert parse_response(server.send("GET", "/api/projects/my-video", cookie=False)).json()["error"]["kind"] == "stale_link"
        server.send("POST", "/api/projects", {"name": "My Video"})
        assert parse_response(server.send("GET", "/api/projects/nope")).status == 404
        server.send("PUT", "/api/projects/my-video/script", {"text": "x"})
        answer = parse_response(server.send("GET", "/api/projects/my-video"))
        assert answer.status == 200
        detail = answer.json()
    assert [(s["ordinal"], s["characters"]) for s in detail["script"]["scenes"]] == [(1, 5), (2, 6)]
    assert detail["script"]["total_characters"] == 11 and len(detail["script"]["revision"]) == 64
    assert detail["can"]["synth"]["all"] is True and detail["kept_backups"] is False
    assert len(stub.calls()) == 1 and stub.recording()["argv"][:3] == ["plan", "--progress", "json"]  # one plan, the stub answered
    assert os.listdir(launch) == []


def test_audio_through_the_server_honours_a_range_and_a_head_and_never_reaches_other_files(loopback_only, stub_cli, tmp_path):
    payload = bytes(range(200))
    workspace = tmp_path / "ws"
    with running(stub_cli(stdout=STATUS_STDOUT), tmp_path, workspace) as server:
        server.send("POST", "/api/projects", {"name": "My Video"})
        (workspace / "my-video" / "audio").mkdir()
        (workspace / "my-video" / "audio" / "001.wav").write_bytes(payload)
        (workspace / "my-video" / "script.md").write_text("secret script")

        def get(method, path, *extra):
            lines = [f"{method} {path} HTTP/1.0", f"Host: 127.0.0.1:{server.port}", f"Cookie: {cookie_name(server.port)}={server.token}", *extra]
            return parse_response(raw_exchange(server.port, ("\r\n".join(lines) + "\r\n\r\n").encode()))

        ranged = get("GET", "/api/projects/my-video/audio/001.wav", "Range: bytes=10-19")
        assert (ranged.status, ranged.body) == (206, payload[10:20])
        assert ranged.one("content-range") == "bytes 10-19/200"
        assert (ranged.one("content-type"), ranged.one("accept-ranges"), ranged.one("cache-control")) == ("audio/wav", "bytes", "no-store")
        head = get("HEAD", "/api/projects/my-video/audio/001.wav")
        assert (head.status, head.body, head.one("content-length")) == (200, b"", "200")
        assert get("GET", "/api/projects/my-video/audio/..%2Fscript.md").status == 404
        assert b"secret script" not in get("GET", "/api/projects/my-video/audio/../script.md").body


def test_the_pack_zip_through_the_server_is_an_attachment_behind_the_cookie_with_only_the_pack_files(loopback_only, stub_cli, tmp_path):
    workspace = tmp_path / "ws"
    with running(stub_cli(stdout=STATUS_STDOUT), tmp_path, workspace) as server:
        server.send("POST", "/api/projects", {"name": "My Video"})
        project = workspace / "my-video"
        assert parse_response(server.send("GET", "/api/projects/my-video/pack.zip")).status == 404  # nothing packed yet
        (project / "audio").mkdir()
        (project / "scene_manifest.csv").write_bytes(b"manifest")
        (project / "audio" / "001.wav").write_bytes(b"wav")
        (project / "script.md").write_text("secret script")
        assert parse_response(server.send("GET", "/api/projects/my-video/pack.zip", cookie=False)).json()["error"]["kind"] == "stale_link"
        response = parse_response(server.send("GET", "/api/projects/my-video/pack.zip"))
        assert response.status == 200
        assert (response.one("content-type"), response.one("cache-control")) == ("application/zip", "no-store")
        assert response.one("content-disposition") == 'attachment; filename="my-video.zip"'
        archive = zipfile.ZipFile(io.BytesIO(response.body))
        assert archive.namelist() == ["my-video/audio/001.wav", "my-video/scene_manifest.csv"]
        assert archive.read("my-video/audio/001.wav") == b"wav"


def test_reveal_through_the_server_needs_the_cookie_posts_only_and_launches_the_recorded_argv_once(loopback_only, stub_cli, tmp_path):
    workspace = tmp_path / "ws"
    launched: list[list[str]] = []

    def record(argv):
        launched.append(list(argv))
        return 0

    with running(stub_cli(stdout=STATUS_STDOUT), tmp_path, workspace, launch=record, platform="darwin") as server:
        server.send("POST", "/api/projects", {"name": "My Video"})
        assert parse_response(server.send("POST", "/api/projects/my-video/reveal", {}, cookie=False)).json()["error"]["kind"] == "stale_link"
        assert launched == []
        wrong = parse_response(server.send("GET", "/api/projects/my-video/reveal"))
        assert (wrong.status, wrong.one("Allow")) == (405, "POST")
        assert launched == []
        response = parse_response(server.send("POST", "/api/projects/my-video/reveal", {}))
        assert (response.status, response.json()) == (200, {"ok": True})
        assert launched == [["open", str((workspace / "my-video").resolve())]]
        assert parse_response(server.send("POST", "/api/projects/nope/reveal", {})).status == 404
        assert len(launched) == 1
