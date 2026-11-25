import os
import stat
from pathlib import Path

from .is_project_id import is_project_id
from .regular_file import regular_file


def _modified(root: Path, project_id: str) -> int | None:
    directory = root / project_id
    try:
        folder = os.lstat(directory)
    except OSError:
        return None  # gone since the listing
    if not stat.S_ISDIR(folder.st_mode):
        return None
    script = regular_file(directory, "script.md")
    try:
        return int(os.lstat(script).st_mtime) if script is not None else int(folder.st_mtime)
    except OSError:
        return int(folder.st_mtime)


def list_projects(root: Path) -> list[dict[str, object]]:
    """The projects under `root`: real directories whose exact name is a project id, newest first, then by id.

    A missing root is an empty list. Entries come from the listing itself, so every id is a byte-exact entry.
    """
    try:
        names = os.listdir(root)
    except FileNotFoundError:
        return []
    projects: list[dict[str, object]] = []
    for name in names:
        if not is_project_id(name):
            continue
        modified = _modified(root, name)
        if modified is not None:
            projects.append({"id": name, "modified": modified})
    projects.sort(key=lambda entry: (-int(str(entry["modified"])), str(entry["id"])))
    return projects
