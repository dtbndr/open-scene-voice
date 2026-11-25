from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from .cli_result import CliResult
from .run_cli import run_cli


def bind_runner(cwd: Path, env: Mapping[str, str], prefix: Sequence[str] | None) -> Callable[..., CliResult]:
    """A runner with the cwd, environment and prefix fixed; callers add stdin and, if needed, a timeout."""

    def run(args: Sequence[str], stdin: bytes | None = None, timeout: float = 30.0) -> CliResult:
        return run_cli(args, cwd=cwd, env=env, stdin=stdin, prefix=prefix, timeout=timeout)

    return run
