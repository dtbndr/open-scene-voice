from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path


def walk(directory: Traversable, prefix: str, found: dict[str, bytes]) -> None:
    for entry in directory.iterdir():
        if entry.name.startswith(".") or (isinstance(entry, Path) and entry.is_symlink()):
            continue
        if entry.is_dir():
            walk(entry, f"{prefix}{entry.name}/", found)
        elif entry.is_file():
            found[f"{prefix}{entry.name}"] = entry.read_bytes()


def build_allowlist(root: Traversable | None = None) -> dict[str, bytes]:
    """Relative path -> bytes of every regular, non-dot, non-symlink file; built once, the only thing ever served."""
    directory = files("scenevoice.web") / "static" if root is None else root
    found: dict[str, bytes] = {}
    if directory.is_dir():
        walk(directory, "", found)
    return found
