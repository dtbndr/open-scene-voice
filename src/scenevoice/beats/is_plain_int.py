"""Integer test that rejects booleans."""

from typing import Any


def is_plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
