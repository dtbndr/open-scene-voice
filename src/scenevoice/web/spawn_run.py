import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from .running_child import RunningChild


def spawn_run(argv: Sequence[str], *, cwd: Path, env: Mapping[str, str]) -> RunningChild:
    """Start one CLI run: no shell, no stdin, piped output, and its own process group (and session)."""
    proc = subprocess.Popen(
        list(argv),
        shell=False,
        cwd=cwd,
        env=dict(env),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    return RunningChild(proc)
