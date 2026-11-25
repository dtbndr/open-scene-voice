import os
from pathlib import Path


def build_beats_argv(script_copy: Path, candidate: Path, model: str) -> list[str]:
    """The arguments (after the interpreter prefix) of `beats`: the private script copy, `--out` the candidate, the model, `--progress json`.

    Absolute paths; the model is a free-text value, so it uses the `=` form and can never be read as a flag. `--out`
    takes its own path argument, which starts with a slash and so cannot be mistaken for a flag either.
    """
    return ["beats", os.path.abspath(script_copy), "--out", os.path.abspath(candidate), f"--model={model}", "--progress", "json"]
