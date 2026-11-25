"""Plain helpers shared across test files (fixtures live in conftest.py)."""

import io
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path


def run(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    input: str | bytes | None = None,
    timeout: float = 60,
) -> subprocess.CompletedProcess:
    """Run the installed `scenevoice` script (next to the interpreter) in a subprocess.

    Output is captured as text unless `input` is bytes. `env` replaces the whole
    environment when given; otherwise the test process environment is inherited.
    A run longer than `timeout` seconds raises subprocess.TimeoutExpired, so a hung
    CLI fails the test instead of stalling the suite.
    """
    script = Path(os.path.dirname(sys.executable)) / "scenevoice"
    return subprocess.run(
        [str(script), *argv],
        capture_output=True,
        text=not isinstance(input, bytes),
        cwd=cwd,
        env=None if env is None else dict(env),
        input=input,
        timeout=timeout,
    )


def plan_bytes(scenes: Sequence[dict] | int = 1, body: str = "hello") -> bytes:
    """Plan JSON as bytes: a list of scene dicts as given, or `n` generated scenes."""
    if isinstance(scenes, int):
        scenes = [{"ordinal": i, "title": "T", "body": body} for i in range(1, scenes + 1)]
    return json.dumps({"scenes": list(scenes)}).encode("utf-8")


class Stdin:
    """A fake `sys.stdin`: `data` (str or bytes) on `.buffer`; `isatty()` returns `tty`."""

    def __init__(self, data: str | bytes = "", tty: bool = False) -> None:
        self.buffer = io.BytesIO(data.encode("utf-8") if isinstance(data, str) else data)
        self.tty = tty

    def isatty(self) -> bool:
        return self.tty
