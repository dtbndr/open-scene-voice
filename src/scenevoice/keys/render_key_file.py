from collections.abc import Mapping

from scenevoice.keys.key_names import KEY_NAMES
from scenevoice.keys.quote_key_value import quote_key_value


def render_key_file(values: Mapping[str, str]) -> str:
    """One `NAME='value'` line per known name present in `values`, in KEY_NAMES order."""
    return "".join(f"{name}={quote_key_value(values[name])}\n" for name in KEY_NAMES if name in values)
