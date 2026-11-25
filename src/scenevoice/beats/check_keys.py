"""Exact key-set check for one mapping level."""

from typing import Any


def check_keys(where: str, obj: dict[Any, Any], expected: tuple[str, ...]) -> str | None:
    for key in expected:
        if key not in obj:
            return f"{where}: missing key {key!r}"
    for key in obj:
        if key not in expected:
            return f"{where}: unexpected key {key!r}"
    return None
