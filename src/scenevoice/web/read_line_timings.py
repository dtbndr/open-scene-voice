import re
from pathlib import Path

from .read_json_file import read_json_file
from .timings_read import TimingsRead

TIMINGS_CAP = 8 * 1024 * 1024
TIMINGS_NAME = "line_timings.json"
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _text(lines: object) -> str | None:
    if not isinstance(lines, list):
        return None
    texts = []
    for line in lines:
        text = line.get("text") if isinstance(line, dict) else None
        if not isinstance(text, str):
            return None
        texts.append(text)
    return " ".join(texts)


def read_line_timings(directory: Path, key_file: Path | None) -> TimingsRead:
    """`line_timings.json` read bounded (8 MiB): per ordinal the entry's sha256 and its line texts joined by a space.

    `none` when absent; `unreadable` for any wrong shape, a repeated ordinal, over-cap or malformed content. One flat
    pass over the scenes and their lines; nothing is walked recursively.
    """
    read = read_json_file(directory, TIMINGS_NAME, TIMINGS_CAP, key_file)
    if read.state != "ok":
        return TimingsRead(read.state)
    document = read.value
    scenes = document.get("scenes") if isinstance(document, dict) and set(document) == {"scenes"} else None
    if not isinstance(scenes, list):
        return TimingsRead("unreadable")
    entries: dict[int, tuple[str, str]] = {}
    for scene in scenes:
        if not isinstance(scene, dict) or set(scene) != {"ordinal", "sha256", "lines"}:
            return TimingsRead("unreadable")
        ordinal, sha256, text = scene["ordinal"], scene["sha256"], _text(scene["lines"])
        if type(ordinal) is not int or ordinal in entries or text is None:
            return TimingsRead("unreadable")
        if not isinstance(sha256, str) or _SHA256.fullmatch(sha256) is None:
            return TimingsRead("unreadable")
        entries[ordinal] = (sha256, text)
    return TimingsRead("ok", entries)
