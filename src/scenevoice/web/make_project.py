import os
from pathlib import Path

from .slugify_name import slugify_name

_MAX = 64


def make_project(root: Path, name: str) -> str:
    """Create the project folder for `name` under `root` (made if missing) and return its id.

    A taken slug gets `-2`, `-3`, ...; names differing only by case count as taken. The atomic `mkdir` without
    `exist_ok` decides, so two requests can never share a folder.
    """
    base = slugify_name(name)
    root.mkdir(parents=True, exist_ok=True)
    taken = {entry.casefold() for entry in os.listdir(root)}
    number = 1
    while True:
        suffix = "" if number == 1 else f"-{number}"
        candidate = base[: _MAX - len(suffix)].strip("-") + suffix
        number += 1
        if candidate.casefold() in taken:
            continue
        try:
            os.mkdir(root / candidate)
        except FileExistsError:
            continue
        return candidate
