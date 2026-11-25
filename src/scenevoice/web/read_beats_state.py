from pathlib import Path

from .beats_light_check import beats_light_check
from .read_json_file import read_json_file

BEATS_CAP = 1024 * 1024


def read_beats_state(directory: Path, revision: str | None, key_file: Path | None) -> str:
    """The beats sidecar state: `none`, `fresh`, `stale` or `invalid`.

    Fresh when its `script_sha256` equals `revision` (the SHA-256 of `script.md`; None with no script is always
    stale); invalid when it is unreadable (not an ordinary file, over 1 MiB, malformed) or fails the light check.
    """
    read = read_json_file(directory, "beats.json", BEATS_CAP, key_file)
    if read.state == "none":
        return "none"
    sha256 = beats_light_check(read.value) if read.state == "ok" else None
    if sha256 is None:
        return "invalid"
    return "fresh" if sha256 == revision else "stale"
