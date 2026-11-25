import subprocess
from collections.abc import Callable, Sequence

# The one launcher shape: argv in, exit code out (non-zero or -1 is failure); it may also raise OSError.
Launch = Callable[[Sequence[str]], int]
OPENER_TIMEOUT = 10.0


def run_opener(argv: Sequence[str]) -> int:
    """Run the platform opener as a child with an argument list and no shell; the exit code, or -1 on failure.

    This is the launcher `run_web` hands to the reveal route. A timeout or an OSError (no such program, no
    permission) is returned as -1, never raised, so the route only has to look at one number.
    """
    try:
        done = subprocess.run(
            list(argv),
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=OPENER_TIMEOUT,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return -1
    return done.returncode
