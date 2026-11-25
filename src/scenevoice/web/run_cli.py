import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from .cli_argv_prefix import cli_argv_prefix
from .cli_result import CliResult


def run_cli(
    args: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    stdin: bytes | None = None,
    prefix: Sequence[str] | None = None,
    timeout: float = 30.0,
) -> CliResult:
    """Run the CLI as a child with an argument list and no shell; the stdin bytes never leave this call."""
    argv = [*(prefix if prefix is not None else cli_argv_prefix()), *args]
    try:
        done = subprocess.run(
            argv,
            shell=False,
            cwd=cwd,
            env=dict(env),
            input=stdin,
            stdin=None if stdin is not None else subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CliResult(-1, "", "", True)
    try:
        return CliResult(done.returncode, done.stdout.decode("utf-8"), done.stderr.decode("utf-8"), False)
    except UnicodeDecodeError:
        return CliResult(-1, "", "", False)
