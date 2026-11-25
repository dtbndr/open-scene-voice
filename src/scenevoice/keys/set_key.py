from collections.abc import Callable
from pathlib import Path

from scenevoice.keys.check_key_value import check_key_value
from scenevoice.keys.key_names import KEY_NAMES
from scenevoice.keys.read_key_file import read_key_file
from scenevoice.keys.unknown_key_violation import unknown_key_violation
from scenevoice.keys.write_key_file import write_key_file
from scenevoice.validation import Violation


def set_key(
    path: str | Path, name: str, raw_value: str, warn: Callable[[str], None] | None
) -> Violation | None:
    """Save `raw_value` under `name`, keeping the other saved names.
    Refuses an unknown name or a bad value before touching the file, and fails without
    writing when the existing file cannot be read. Blank values and unknown lines in the
    existing file are dropped on rewrite. Messages carry names and paths only."""
    if name not in KEY_NAMES:
        return unknown_key_violation(name)
    problem = check_key_value(name, raw_value)
    if problem is not None:
        return Violation("key-file", problem)
    existing = read_key_file(path, warn)
    if isinstance(existing, Violation):
        return existing
    values = {key: value for key, value in existing.items() if value.strip() != ""}
    values[name] = raw_value
    return write_key_file(path, values)
