from collections.abc import Mapping

from scenevoice.keys.key_names import KEY_NAMES


def child_env(environ: Mapping[str, str]) -> dict[str, str]:
    """Copy of `environ` without the provider key names (denylist); the input is not mutated."""
    return {name: value for name, value in environ.items() if name not in KEY_NAMES}
