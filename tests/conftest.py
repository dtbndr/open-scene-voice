"""Suite-wide guard: no test may read or write a real per-user key file."""

import socket
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_key_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCENEVOICE_KEYS_FILE", str(tmp_path / "keys-guard" / "keys.env"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


@pytest.fixture
def no_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any test that tries to open a real network connection."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a test tried to open a real connection")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)


@pytest.fixture
def clean_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_sockets: None) -> Path:
    """Work in an empty tmp dir with no provider key in the process environment."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    return tmp_path


@pytest.fixture
def key_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., Path]:
    """Return a writer: `key_file(text, mode=0o600, name="keys")` creates a keys file and points the env at it."""

    def write(text: str, mode: int = 0o600, name: str = "keys") -> Path:
        path = tmp_path / name / "keys.env"
        path.parent.mkdir()
        path.write_text(text, encoding="utf-8")
        path.chmod(mode)
        monkeypatch.setenv("SCENEVOICE_KEYS_FILE", str(path))
        return path

    return write
