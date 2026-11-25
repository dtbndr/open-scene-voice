"""Helpers for the project detail tests: a project folder on disk and a fake plan runner (no child process)."""

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

from record_helper import eleven_entry, gemini_entry, write_record

from scenevoice.web import CliResult


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def plan_stdout(bodies: list[str]) -> str:
    scenes = [{"ordinal": n, "title": f"Scene {n}", "body": body} for n, body in enumerate(bodies, 1)]
    return json.dumps({"scenes": scenes}, ensure_ascii=False) + "\n"


class FakePlan:
    """Stands in for the bound CLI runner: answers a canned plan result and counts the calls."""

    def __init__(self, result: CliResult) -> None:
        self.result = result
        self.calls: list[list[str]] = []

    def __call__(self, args: Any, stdin: Any = None, timeout: float = 30.0) -> CliResult:
        self.calls.append(list(args))
        return self.result


def passing(bodies: list[str]) -> FakePlan:
    return FakePlan(CliResult(0, plan_stdout(bodies), "", False))


def failing_script(line: int = 4, message: str = "Scene 2 is empty") -> FakePlan:
    class WithPath(FakePlan):
        def __call__(self, args: Any, stdin: Any = None, timeout: float = 30.0) -> CliResult:
            self.calls.append(list(args))
            event = {"event": "fail", "kind": "invalid_input", "message": f"{args[-1]}: {message} (line {line})", "line": line}
            return CliResult(1, "", json.dumps(event), False)

    return WithPath(CliResult(1, "", "", False))


def put_wavs(directory: Path, wavs: dict[int, bytes]) -> None:
    (directory / "audio").mkdir(exist_ok=True)
    for ordinal, data in wavs.items():
        (directory / "audio" / f"{ordinal:03d}.wav").write_bytes(data)


def put_record(directory: Path, bodies: list[str], wavs: dict[int, bytes], eleven: bool = False) -> None:
    entries = [
        eleven_entry(n, data, bodies[n - 1]) if eleven else gemini_entry(n, data) for n, data in sorted(wavs.items())
    ]
    write_record(directory, *entries)


def snapshot(directory: Path) -> dict[str, tuple[int, int, bytes | None]]:
    """Every entry under `directory` with its mode, mtime in ns and bytes: equal before and after means nothing written."""
    state: dict[str, tuple[int, int, bytes | None]] = {}
    for root, names, files in os.walk(directory):
        for name in [*names, *files]:
            path = Path(root) / name
            info = os.lstat(path)
            state[str(path.relative_to(directory))] = (
                stat.S_IMODE(info.st_mode), info.st_mtime_ns, path.read_bytes() if stat.S_ISREG(info.st_mode) else None,
            )
    return state
