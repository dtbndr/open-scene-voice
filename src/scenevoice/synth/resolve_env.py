from collections.abc import Mapping, Sequence
from pathlib import Path

from dotenv import dotenv_values

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
) -> dict[str, str] | list[str] | Violation:
    """Process value wins, then `.env`; blank counts as unset. Names only on failure."""
    try:
        file_env = dotenv_values(dotenv_path, interpolate=False)
    except (OSError, UnicodeDecodeError):
        return Violation(_RULE, "could not read .env")
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for name in names:
        for source in (process_env.get(name), file_env.get(name)):
            if _usable(source):
                resolved[name] = source  # type: ignore[assignment]
                break
        else:
            missing.append(name)
    return missing or resolved
