from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JsonRead:
    """A bounded JSON file read: state `none` (no such entry), `ok` (value parsed) or `unreadable` (anything else)."""

    state: str
    value: Any = None
