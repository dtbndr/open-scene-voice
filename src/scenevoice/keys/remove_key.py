from collections.abc import Callable
from pathlib import Path
from typing import Literal

from scenevoice.keys.key_names import KEY_NAMES
from scenevoice.keys.read_key_file import read_key_file
from scenevoice.keys.unknown_key_violation import unknown_key_violation
from scenevoice.keys.write_key_file import write_key_file
from scenevoice.validation import Violation


def remove_key(
    path: str | Path, name: str, warn: Callable[[str], None] | None
) -> Violation | Literal["removed", "absent"]:
    """Remove `name` from the key file: "removed", "absent" (not saved, nothing written;
    a blank entry counts as not saved) or a Violation. Removing the last name leaves an
    empty file. Blank values and unknown lines are dropped when the file is rewritten.
    Messages carry names and paths only."""
    if name not in KEY_NAMES:
        return unknown_key_violation(name)
    existing = read_key_file(path, warn)
    if isinstance(existing, Violation):
        return existing
    values = {key: value for key, value in existing.items() if value.strip() != ""}
    if name not in values:
        return "absent"
    del values[name]
    written = write_key_file(path, values)
    return written if written is not None else "removed"
