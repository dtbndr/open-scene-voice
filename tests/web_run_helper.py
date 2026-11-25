"""Helpers for the run_web tests: a recording opener and serve, and the printed link."""

import re
import socket
from pathlib import Path
from typing import Any

import pytest

from scenevoice.web import bind_socket, run_web


class Recorder:
    def __init__(self, capsys: pytest.CaptureFixture[str], launch_root: Path) -> None:
        self.capsys = capsys
        self.launch_root = launch_root
        self.out = ""
        self.err = ""
        self.opened: list[str] = []
        self.served: list[Any] = []
        self.opener_saw: dict[str, Any] = {}
        self.serve_saw: dict[str, Any] = {}

    def opener(self, link: str) -> bool:
        self.out += self.capsys.readouterr().out
        self.opened.append(link)
        port = int(re.search(r":(\d+)/", link).group(1))  # type: ignore[union-attr]
        socket.create_connection(("127.0.0.1", port), timeout=2).close()
        self.opener_saw["printed_first"] = "Open it here" in self.out
        return True

    def serve(self, server: Any) -> None:
        self.served.append(server)
        self.serve_saw["launch_dirs"] = sorted(path.name for path in self.launch_root.iterdir())

    def run(self, **options: Any) -> int:
        arguments: dict[str, Any] = {
            "port": 0, "no_open": False, "opener": self.opener, "environ": {}, "serve": self.serve,
        }
        code = run_web(**{**arguments, **options})
        captured = self.capsys.readouterr()
        self.out += captured.out
        self.err += captured.err
        return code

    def link(self) -> str:
        found = re.search(r"Open it here: (\S+)", self.out)
        assert found
        return found.group(1)


def occupy_port() -> socket.socket:
    held = bind_socket(0)
    held.listen()
    return held


__all__ = ["Recorder", "occupy_port"]
