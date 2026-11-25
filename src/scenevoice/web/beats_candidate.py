import os
import secrets
from pathlib import Path


def beats_candidate(directory: Path) -> Path:
    """A new candidate path `.write-beats-<hex>.tmp` in the project folder (never the launch directory: `os.replace` needs one volume).

    The name does not exist yet (a symlink, even a dangling one, counts as existing); the file is not created here,
    the CLI creates it exclusively. The `.write-*.tmp` shape is the one every reader and allowlist already ignores.
    """
    while True:
        path = directory / f".write-beats-{secrets.token_hex(8)}.tmp"
        if not os.path.lexists(path):
            return path
