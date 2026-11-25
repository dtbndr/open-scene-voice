import re
from pathlib import Path

from .read_json_file import read_json_file
from .record_item import RecordItem
from .record_read import RecordRead
from .white_space import WHITE_SPACE_RUN

RECORD_CAP = 32 * 1024 * 1024
RECORD_NAME = "synth_record.json"
_KEYS = {"ordinal", "sha256", "voice", "model", "language", "instruction", "alignment"}
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _name(value: object) -> bool:
    return isinstance(value, str) and WHITE_SPACE_RUN.sub("", value) != ""


def _optional(value: object) -> bool:
    return value is None or isinstance(value, str)


def _item(entry: object, previous: int) -> RecordItem | None:
    if not isinstance(entry, dict) or set(entry) != _KEYS:
        return None
    ordinal, sha256, alignment = entry["ordinal"], entry["sha256"], entry["alignment"]
    if type(ordinal) is not int or ordinal < 1 or ordinal <= previous:
        return None
    if not isinstance(sha256, str) or _SHA256.fullmatch(sha256) is None:
        return None
    if not (_name(entry["voice"]) and _name(entry["model"]) and _optional(entry["language"]) and _optional(entry["instruction"])):
        return None
    characters: str | None = None
    if alignment is not None:
        letters = alignment.get("characters") if isinstance(alignment, dict) else None
        if not isinstance(letters, list) or not all(isinstance(letter, str) for letter in letters):
            return None
        characters = "".join(letters)
    return RecordItem(ordinal, sha256, entry["voice"], entry["model"], entry["language"], entry["instruction"], characters)


def read_record(directory: Path, key_file: Path | None) -> RecordRead:
    """`synth_record.json` read bounded (32 MiB) through the no-follow helper: fixed keys only, one flat pass.

    `none` when absent, `unreadable` for any wrong shape, over-cap or malformed file. Ordinals must be positive and
    strictly increasing, as the CLI's own parser requires.
    """
    read = read_json_file(directory, RECORD_NAME, RECORD_CAP, key_file)
    if read.state != "ok":
        return RecordRead(read.state)
    document = read.value
    scenes = document.get("scenes") if isinstance(document, dict) and set(document) == {"scenes"} else None
    if not isinstance(scenes, list):
        return RecordRead("unreadable")
    items: list[RecordItem] = []
    previous = 0
    for entry in scenes:
        parsed = _item(entry, previous)
        if parsed is None:
            return RecordRead("unreadable")
        items.append(parsed)
        previous = parsed.ordinal
    return RecordRead("ok", tuple(items))
