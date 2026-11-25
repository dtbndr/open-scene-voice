import os
from pathlib import Path


def build_pack_argv(plan_file: Path, directory: Path) -> list[str]:
    """The arguments (after the interpreter prefix) of `pack` for DaVinci Resolve: the counted plan file and the project folder, absolute."""
    return ["pack", "--editor", "resolve", "--progress", "json", os.path.abspath(plan_file), os.path.abspath(directory)]
