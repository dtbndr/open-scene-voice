"""Fixtures for the web package: a loopback-only socket guard and a recording CLI stub."""

import base64
import json
import shutil
import socket
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from web_run_helper import Recorder

STUB_SOURCE = Path(__file__).with_name("stub_cli.py")
RECORDED_ENV = (
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "VERTEX_AUTHORIZATION_KEY",
    "ELEVENLABS_API_KEY",
    "OPENROUTER_API_KEY",
    "SCENEVOICE_KEYS_FILE",
    "XDG_CONFIG_HOME",
    "APPDATA",
    "HOME",
    "HTTPS_PROXY",
    "SSL_CERT_FILE",
)


@pytest.fixture
def loopback_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow connect and bind only for 127.0.0.1; any other address raises.

    Never combine with `no_sockets`: that fixture refuses every connect, this one allows loopback.
    """
    real_connect = socket.socket.connect
    real_bind = socket.socket.bind

    def guard(real: Callable[..., Any]) -> Callable[..., Any]:
        def checked(self: socket.socket, address: Any, *args: Any) -> Any:
            if not (isinstance(address, tuple) and address and address[0] == "127.0.0.1"):
                raise AssertionError("a test used an address other than 127.0.0.1")
            return real(self, address, *args)

        return checked

    def refuse_create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
        if address[0] != "127.0.0.1":
            raise AssertionError("a test used an address other than 127.0.0.1")
        return real_create_connection(address, *args, **kwargs)

    real_create_connection = socket.create_connection
    monkeypatch.setattr(socket.socket, "connect", guard(real_connect))
    monkeypatch.setattr(socket.socket, "bind", guard(real_bind))
    monkeypatch.setattr(socket, "create_connection", refuse_create_connection)


@dataclass(frozen=True)
class StubCli:
    prefix: list[str]
    recording_path: Path

    def recording(self) -> dict[str, Any]:
        data = json.loads(self.recording_path.read_text(encoding="utf-8"))
        data["stdin"] = base64.b64decode(data.pop("stdin_b64"))
        return data

    def calls(self) -> list[dict[str, Any]]:
        """Every recorded call in order (recording() keeps only the last)."""
        path = self.recording_path.parent / "calls.jsonl"
        calls = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
        for call in calls:
            call["stdin"] = base64.b64decode(call.pop("stdin_b64"))
        return calls

    def events(self) -> list[dict[str, Any]]:
        path = self.recording_path.parent / "events.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def stub_cli(tmp_path: Path) -> Callable[..., StubCli]:
    """Return a factory: `stub_cli(stdout=..., stderr_lines=[...], exit_code=0, ...)` writes the stub and its spec."""

    def make(**spec: Any) -> StubCli:
        directory = tmp_path / "stub"
        directory.mkdir(exist_ok=True)
        script = directory / "stub_cli.py"
        shutil.copyfile(STUB_SOURCE, script)
        (directory / "spec.json").write_text(
            json.dumps({"record_env": list(RECORDED_ENV), **spec}), encoding="utf-8"
        )
        return StubCli([sys.executable, str(script)], directory / "recording.json")

    return make


@pytest.fixture
def recorder(capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, loopback_only: None) -> Recorder:
    root = tmp_path / "launch-root"
    root.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(root))
    return Recorder(capsys, root)


@pytest.fixture
def fake_listing(monkeypatch: pytest.MonkeyPatch) -> Callable[[str, list[str]], list[str]]:
    """Make `os.listdir` answer a fixed listing for a module's calls; returns the list of directories asked.

    Simulates a case-insensitive volume without depending on the host volume.
    """

    def install(module: str, names: list[str]) -> list[str]:
        asked: list[str] = []
        real_os = sys.modules[f"scenevoice.web.{module}"].os

        def fake(directory: Any = ".") -> list[str]:
            asked.append(str(directory))
            return list(names)

        monkeypatch.setattr(real_os, "listdir", fake)
        return asked

    return install


@pytest.fixture
def killpgs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int]]:
    """Record every `os.killpg` made through the runner's child handle; the real call still happens."""
    module = sys.modules["scenevoice.web.running_child"]
    calls: list[tuple[int, int]] = []
    real = module.os.killpg

    def recording(pgid: int, sig: int) -> None:
        calls.append((pgid, sig))
        real(pgid, sig)

    monkeypatch.setattr(module.os, "killpg", recording)
    return calls
