"""Fixtures shared by the CLI tests."""

import io
import os
import sys
from pathlib import Path

import pytest


class _Tracked(io.BytesIO):
    reads = 0

    def read(self, *args, **kwargs):  # type: ignore[override]
        type(self).reads += 1
        return super().read(*args, **kwargs)


class FakeStdin:
    def __init__(self, data: bytes, tty: bool = False) -> None:
        self.buffer = _Tracked(data)
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


@pytest.fixture
def key_path() -> Path:
    """The guarded per-user key file path (not created); its folder exists."""
    path = Path(os.environ["SCENEVOICE_KEYS_FILE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def feed(monkeypatch):
    """Replace stdin with fixed bytes; `_Tracked.reads` counts reads of the buffer."""

    def _feed(data: bytes, tty: bool = False) -> FakeStdin:
        _Tracked.reads = 0
        fake = FakeStdin(data, tty)
        monkeypatch.setattr(sys, "stdin", fake)
        return fake

    return _feed


class FailingStdin:
    def __init__(self):
        self.touched = []

    @property
    def buffer(self):
        self.touched.append("buffer")
        raise AssertionError("stdin was read")

    def isatty(self):
        self.touched.append("isatty")
        raise AssertionError("stdin was probed")

    def read(self, *args):
        self.touched.append("read")
        raise AssertionError("stdin was read")


@pytest.fixture
def probes(tmp_path, monkeypatch):
    """Isolated cwd with a plan and .env; records every file open and factory call."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "plan.json").write_text('{"scenes": []}')
    (tmp_path / ".env").write_text("GOOGLE_CLOUD_PROJECT=p\n")
    stdin = FailingStdin()
    monkeypatch.setattr("sys.stdin", stdin)
    opened = []
    real_open = io.open

    def spy_open(file, *args, **kwargs):
        opened.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(io, "open", spy_open)
    factory_calls = []

    def factory(env, model):
        factory_calls.append(env)
        raise AssertionError("factory called")

    class Probes:
        pass

    p = Probes()
    p.stdin, p.opened, p.factory_calls, p.factory, p.out = (
        stdin, opened, factory_calls, factory, tmp_path / "out")
    return p
