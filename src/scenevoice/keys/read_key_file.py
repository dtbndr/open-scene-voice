from collections.abc import Callable
from pathlib import Path

from dotenv.parser import parse_stream

from scenevoice.keys.key_names import KEY_NAMES
from scenevoice.keys.loose_permission_problem import loose_permission_problem
from scenevoice.validation import Violation
from scenevoice.validation.regular_file_problem import regular_file_problem

_RULE = "key-file"


def read_key_file(
    path: str | Path, warn: Callable[[str], None] | None
) -> dict[str, str] | Violation:
    """Raw values of the known names in `path`; missing file is `{}`. Blank values are kept.
    Messages carry names and paths only, never a value."""
    if regular_file_problem(path) is not None:
        return Violation(_RULE, f"key file {path} is not a regular file")
    try:
        with open(path, encoding="utf-8") as stream:
            bindings = list(parse_stream(stream))
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError):
        return Violation(_RULE, f"could not read key file {path}")
    if warn is not None and (loose := loose_permission_problem(path)) is not None:
        warn(loose)
    for binding in bindings:
        if binding.error:
            return Violation(_RULE, f"key file {path}: line {binding.original.line} is not NAME=value")
    return {
        b.key: b.value or ""
        for b in bindings
        if b.key in KEY_NAMES
    }
