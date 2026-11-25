import os
from pathlib import Path


def build_synth_argv(
    plan_file: Path, directory: Path, *, voice: str, model: str, language: str | None, instruction: str | None, scene: int | None
) -> list[str]:
    """The arguments (after the interpreter prefix) of `synth`: absolute paths, every setting in the `--name=value` form.

    The `=` form keeps a value that starts with `-` a value, never a flag. The list is passed to the child directly
    (no shell), and `--progress json` is last so the server reads the child's events.
    """
    argv = ["synth", os.path.abspath(plan_file), "--out", os.path.abspath(directory), f"--voice={voice}", f"--model={model}"]
    if language is not None:
        argv.append(f"--language={language}")
    if instruction is not None:
        argv.append(f"--instruction={instruction}")
    if scene is not None:
        argv.append(f"--scene={scene}")
    return [*argv, "--progress", "json"]
