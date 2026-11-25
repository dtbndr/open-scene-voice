import json
from pathlib import Path

from .exact_entry import exact_entry
from .json_read import JsonRead
from .read_regular_bytes import read_regular_bytes
from .workspace_error import FileTooLargeError


def read_json_file(directory: Path, name: str, cap: int, key_file: Path | None) -> JsonRead:
    """The JSON document of the byte-exact entry `name` of `directory`: `none` when absent, `unreadable` on any problem.

    Opened through the no-follow helper (regular, singly linked, not the key file), bounded by `cap`, decoded as
    UTF-8 and parsed once with `json.loads`; an over-cap, undecodable, malformed or too deeply nested file is
    `unreadable`, never an error.
    """
    if not exact_entry(directory, name):
        return JsonRead("none")
    try:
        data = read_regular_bytes(directory / name, cap, key_file)
    except FileTooLargeError:
        return JsonRead("unreadable")
    if data is None:
        return JsonRead("unreadable")
    try:
        return JsonRead("ok", json.loads(data.decode("utf-8")))
    except (ValueError, RecursionError):  # UnicodeDecodeError is a ValueError
        return JsonRead("unreadable")
