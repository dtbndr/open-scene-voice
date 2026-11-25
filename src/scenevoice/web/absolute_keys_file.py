from collections.abc import Mapping
from pathlib import Path

_OVERRIDE = "SCENEVOICE_KEYS_FILE"


def absolute_keys_file(environ: Mapping[str, str]) -> dict[str, str]:
    """Copy of `environ` with a non-blank relative key-file override made absolute against this cwd."""
    result = dict(environ)
    override = result.get(_OVERRIDE, "")
    if override.strip():
        result[_OVERRIDE] = str(Path(override).absolute())
    return result
