import os
from pathlib import Path


def exact_entry(directory: Path, name: str) -> bool:
    """True when `name` is a byte-exact entry of `directory`; false for a missing directory."""
    try:
        return name in os.listdir(directory)
    except OSError:
        return False
