import os
import stat
import sys
from pathlib import Path

import pytest

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")

CANARY = "CANARY-SECRET-VALUE-123"
LOOSE = "key file {path} can be read by other users; run chmod 600 {path}"


def mode_of(path: Path) -> int:
    return stat.S_IMODE(os.stat(path).st_mode)


def no_warn(_: str) -> None:
    raise AssertionError("unexpected warning")


def seed(path: Path, text: str = "OPENROUTER_API_KEY='or'\nELEVENLABS_API_KEY='el'\n", mode: int = 0o600) -> bytes:
    path.write_bytes(text.encode())
    path.chmod(mode)
    return path.read_bytes()
