import os
from pathlib import Path


def spelling_conflict(directory: Path, name: str) -> bool:
    """True when `name` is not listed in `directory` but a differently cased spelling of it is."""
    try:
        listed = os.listdir(directory)
    except OSError:
        return False
    return name not in listed and any(entry.casefold() == name.casefold() for entry in listed)
