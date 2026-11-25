"""A light-valid beats sidecar and a project folder with a candidate, for the beats swap tests."""

import hashlib
import json
from pathlib import Path

SCRIPT_BYTES = b"# One\nHello.\n"
REVISION = hashlib.sha256(SCRIPT_BYTES).hexdigest()
OLD = b'{"old": "beats"}'


def sidecar_bytes(revision: str = REVISION, **changes: object) -> bytes:
    document = {"version": 1, "script_sha256": revision, "scenes": [{"scene": 1}], **changes}
    return json.dumps(document).encode("utf-8")


def put_candidate(directory: Path, data: bytes | None = None, name: str = ".write-beats-0123456789abcdef.tmp") -> Path:
    path = directory / name
    path.write_bytes(sidecar_bytes() if data is None else data)
    return path


def put_old_beats(directory: Path) -> Path:
    path = directory / "beats.json"
    path.write_bytes(OLD)
    return path
