import os
from pathlib import Path


def build_align_argv(plan_file: Path, directory: Path) -> list[str]:
    """The arguments (after the interpreter prefix) of `align`: `--progress json`, the counted plan file, the project folder, absolute."""
    return ["align", "--progress", "json", os.path.abspath(plan_file), os.path.abspath(directory)]
