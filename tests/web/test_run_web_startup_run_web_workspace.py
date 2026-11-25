import json
import os
import signal
import socket
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from job_runner_helper import pid_gone, wait_until
from web_http_helper import parse_response, raw_exchange

from scenevoice.web import PortBusyError, bind_socket, cookie_name


@pytest.fixture
def binds(monkeypatch):
    module = sys.modules["scenevoice.web.run_web"]
    calls = []
    real = module.bind_socket

    def counting(port):
        calls.append(port)
        return real(port)

    monkeypatch.setattr(module, "bind_socket", counting)
    return calls


def refused_cleanly(recorder, binds):
    assert recorder.opened == [] and recorder.served == []
    assert binds == []  # the port was never bound
    assert list(recorder.launch_root.iterdir()) == []  # and no launch directory exists


def test_a_valid_start_binds_once_which_is_what_the_refusals_below_prevent(recorder, binds, tmp_path):
    assert recorder.run(workspace=tmp_path / "ws") == 0
    assert len(binds) == 1


def test_a_relative_workspace_variable_is_refused_before_binding(recorder, binds):
    assert recorder.run(environ={"SCENEVOICE_WORKSPACE": "relative/folder"}) == 1
    assert recorder.err.startswith("scenevoice web: ")
    assert "SCENEVOICE_WORKSPACE" in recorder.err and "absolute" in recorder.err
    refused_cleanly(recorder, binds)


def test_an_injected_workspace_is_used_and_never_created_at_launch(recorder, tmp_path):
    workspace = tmp_path / "ws"
    assert recorder.run(workspace=workspace) == 0
    assert not workspace.exists()


@pytest.mark.parametrize("spelling", ["ws", "ws/keys.env", "ws/deeper/keys.env", "WS/Keys.env"])
def test_a_key_file_equal_to_or_inside_the_workspace_is_refused_before_binding(recorder, binds, tmp_path, spelling):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "keys.env").write_text("SECRETMARKER")
    assert recorder.run(workspace=workspace, key_file=tmp_path / spelling) == 1
    assert recorder.err.startswith("scenevoice web: ")
    assert "key file" in recorder.err and "SECRETMARKER" not in recorder.err + recorder.out
    refused_cleanly(recorder, binds)


def test_no_key_file_means_no_check_even_when_the_environment_names_one_inside(recorder, tmp_path):
    workspace = tmp_path / "ws"
    environ = {"SCENEVOICE_KEYS_FILE": str(workspace / "keys.env")}
    assert recorder.run(workspace=workspace, environ=environ, key_file=None) == 0


def test_a_key_file_elsewhere_starts_normally(recorder, tmp_path):
    assert recorder.run(workspace=tmp_path / "ws", key_file=tmp_path / "keys" / "keys.env") == 0


def test_the_project_routes_are_wired_with_the_workspace_the_runner_and_the_launcher(recorder, stub_cli, tmp_path, monkeypatch):
    module = sys.modules["scenevoice.web.run_web"]
    stub = stub_cli(stdout="{}")
    workspace = tmp_path / "ws"
    (workspace / "alpha").mkdir(parents=True)
    key_file = tmp_path / "keys" / "keys.env"
    launcher = object()
    seen = []
    real = module.ProjectRoutes
    monkeypatch.chdir(tmp_path)

    def spy(**options):
        seen.append(options)
        return real(**options)

    monkeypatch.setattr(module, "ProjectRoutes", spy)
    getters = []
    real_getter = module.make_root_getter

    def getter_spy(*arguments):
        getters.append(arguments)
        return real_getter(*arguments)

    monkeypatch.setattr(module, "make_root_getter", getter_spy)
    answer = {}

    def serve(server):
        recorder.served.append(server)
        port = server.server_address[1]
        recorder.out += recorder.capsys.readouterr().out
        token = recorder.link().split("token=")[1]
        worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        worker.start()
        raw = (
            f"GET /api/projects HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\nCookie: {cookie_name(port)}={token}\r\n\r\n"
        ).encode()
        answer["listing"] = parse_response(raw_exchange(port, raw))
        server.shutdown()
        worker.join(5)
        seen[0]["run"](["keys", "status"], None)
        answer["cwd"] = stub.recording()["cwd"]
        answer["env"] = stub.recording()["env"]["SCENEVOICE_KEYS_FILE"]
        answer["launch_dir"] = [str(path.resolve()) for path in recorder.launch_root.iterdir()]

    environ = {"SCENEVOICE_KEYS_FILE": "rel/keys.env"}
    assert recorder.run(workspace=workspace, key_file=key_file, launch=launcher, prefix=stub.prefix, serve=serve, environ=environ) == 0
    assert answer["listing"].status == 200
    assert [entry["id"] for entry in answer["listing"].json()["projects"]] == ["alpha"]
    assert answer["cwd"] == answer["launch_dir"][0]
    assert answer["env"] == str(tmp_path / "rel" / "keys.env")
    assert seen[0]["key_file"] == key_file and seen[0]["launch"] is launcher
    assert seen[0]["root_getter"]() == workspace.resolve()
    assert getters == [(workspace, key_file)]  # WS42-DB-01 (b): the fail-closed check gets the key file


def test_the_project_routes_get_the_launch_directory_the_children_run_in(recorder, stub_cli, tmp_path, monkeypatch):
    module = sys.modules["scenevoice.web.run_web"]
    stub = stub_cli(stdout="{}")
    seen = []
    real = module.ProjectRoutes
    monkeypatch.setattr(module, "ProjectRoutes", lambda **options: (seen.append(options), real(**options))[1])
    answer = {}

    def serve(server):
        recorder.served.append(server)
        seen[0]["run"](["keys", "status"], None)
        answer["cwd"] = stub.recording()["cwd"]

    assert recorder.run(workspace=tmp_path / "ws", prefix=stub.prefix, serve=serve) == 0
    assert answer["cwd"] and str(seen[0]["launch_dir"].resolve()) == answer["cwd"]


def test_binds_loopback_only_and_port_zero_yields_a_real_port(loopback_only):
    sock = bind_socket(0)
    try:
        host, port = sock.getsockname()
        assert host == "127.0.0.1"
        assert port > 0
    finally:
        sock.close()


def test_the_given_port_is_the_bound_port(loopback_only):
    probe = bind_socket(0)
    port = probe.getsockname()[1]
    probe.close()
    sock = bind_socket(port)
    try:
        assert sock.getsockname() == ("127.0.0.1", port)
    finally:
        sock.close()


def test_sets_reuse_address_and_never_reuse_port(loopback_only):
    sock = bind_socket(0)
    try:
        assert sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR) != 0
        assert sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT) == 0
    finally:
        sock.close()


def test_a_live_listener_makes_the_port_busy_with_a_plain_message_and_no_fallback(loopback_only):
    first = bind_socket(0)
    first.listen()
    port = first.getsockname()[1]
    try:
        with pytest.raises(PortBusyError) as raised:
            bind_socket(port)
        message = str(raised.value)
        assert str(port) in message
        assert "--port" in message
    finally:
        first.close()


HARNESS = Path(__file__).with_name("serve_harness.py")


class Harness:
    def __init__(self, tmp_path: Path, stub, **config) -> None:
        self.tmp_path = tmp_path
        self.stub = stub
        self.launch_root = tmp_path / "launch-root"
        self.launch_root.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        settings = {
            "prefix": stub.prefix, "workspace": str(workspace), "kill_delay": 0.3, "job": True,
            "ready": str(tmp_path / "ready"), "result": str(tmp_path / "result.json"), **config,
        }
        (tmp_path / "config.json").write_text(json.dumps(settings), encoding="utf-8")
        self.out = (tmp_path / "harness.out").open("w")
        self.proc = subprocess.Popen(
            [sys.executable, "-B", str(HARNESS), str(tmp_path / "config.json")],
            stdin=subprocess.DEVNULL, stdout=self.out, stderr=subprocess.STDOUT,
            env={**os.environ, "TMPDIR": str(self.launch_root)},
        )
        wait_until(lambda: (tmp_path / "ready").exists() or self.proc.poll() is not None)
        assert self.proc.poll() is None, self.output()

    def finish(self) -> int:
        code = self.proc.wait(timeout=30)
        self.out.close()
        return code

    def output(self) -> str:
        return (self.tmp_path / "harness.out").read_text(encoding="utf-8")

    def assert_clean(self) -> None:
        """The child and its group were gone at the moment the launch directory was removed, and it is gone."""
        result = json.loads((self.tmp_path / "result.json").read_text(encoding="utf-8"))
        assert result == {"child_gone": True, "group_gone": True, "launch_dir_existed": True}
        assert pid_gone(self.stub.recording()["pid"])
        wait_until(lambda: pid_gone(int((self.tmp_path / "grandchild").read_text())))
        assert list(self.launch_root.iterdir()) == []


@pytest.fixture
def start_harness(tmp_path, stub_cli, loopback_only) -> Iterator[Callable[..., Harness]]:
    started: list[Harness] = []

    def start(**config) -> Harness:
        stub = stub_cli(
            sigint="ignore", sigint_marker=str(tmp_path / "sigint-marker"), spawn_grandchild=str(tmp_path / "grandchild"),
            wait_for_file=str(tmp_path / "never"),
        )
        started.append(Harness(tmp_path, stub, **config))
        return started[-1]

    yield start
    for harness in started:
        if harness.proc.poll() is None:
            harness.proc.kill()
            harness.proc.wait(timeout=10)
    grandchild = tmp_path / "grandchild"
    if grandchild.exists() and not pid_gone(int(grandchild.read_text())):
        os.kill(int(grandchild.read_text()), signal.SIGKILL)


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM])
def test_a_stop_signal_stops_the_child_and_its_group_before_the_launch_dir_goes(start_harness, sig):
    harness = start_harness()
    harness.proc.send_signal(sig)
    assert harness.finish() == 0
    harness.assert_clean()
    assert harness.output().rstrip().splitlines()[-1] == "SceneVoice has stopped."


def test_a_second_signal_while_the_runner_is_stopping_a_stubborn_child_changes_nothing(start_harness, tmp_path):
    harness = start_harness(kill_delay=0.6)
    harness.proc.send_signal(signal.SIGINT)
    wait_until(lambda: (tmp_path / "sigint-marker").exists())  # the runner interrupted the child, which ignores it
    harness.proc.send_signal(signal.SIGTERM)
    assert harness.finish() == 0
    harness.assert_clean()
