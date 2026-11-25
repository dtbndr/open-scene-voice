from collections.abc import Mapping

from scenevoice.keys.key_names import KEY_NAMES


def ignored_environment(environ: Mapping[str, str]) -> list[str]:
    """Key variable names set (non-blank) in `environ`, in KEY_NAMES order; names only, never values."""
    return [name for name in KEY_NAMES if environ.get(name, "").strip()]
