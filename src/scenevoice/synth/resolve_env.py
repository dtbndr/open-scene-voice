from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from dotenv import dotenv_values

from scenevoice.keys import read_key_file
from scenevoice.synth.env_names import ENV_NAMES
from scenevoice.synth.is_text_blank import is_text_blank
from scenevoice.validation import Violation

_RULE = "environment"


def _usable(value: str | None) -> bool:
    return value is not None and not is_text_blank(value)


def resolve_env(
    process_env: Mapping[str, str],
    dotenv_path: str | Path,
    names: Sequence[str] = ENV_NAMES,
    *,
    key_file: str | Path | None = None,
    warn: Callable[[str], None] | None = None,
) -> dict[str, str] | list[str] | Violation:
    """Per name: process value, then key file, then `.env`; blank counts as unset.
    A given key file is read eagerly: a broken one fails even if the process supplies
    every name, and a loose-permission warning goes to `warn`. Names only on failure."""
    key_env: Mapping[str, str] = {}
    if key_file is not None:
        key_result = read_key_file(key_file, warn)
        if isinstance(key_result, Violation):
            return key_result
        key_env = key_result
    try:
        file_env = dotenv_values(dotenv_path, interpolate=False)
    except (OSError, UnicodeDecodeError):
        return Violation(_RULE, "could not read .env")
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for name in names:
        for source in (process_env.get(name), key_env.get(name), file_env.get(name)):
            if _usable(source):
                resolved[name] = source  # type: ignore[assignment]
                break
        else:
            missing.append(name)
    return missing or resolved
