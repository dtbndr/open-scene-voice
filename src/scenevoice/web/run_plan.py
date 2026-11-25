import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from .cli_result import CliResult
from .parse_plan_failure import parse_plan_failure
from .parse_plan_scenes import parse_plan_scenes
from .plan_problem import PlanProblem
from .plan_run import PlanRun
from .script_revision import script_revision


def _outcome(result: CliResult, temp_path: str, data: bytes) -> PlanRun | PlanProblem | None:
    if result.timed_out or result.returncode == -1:
        return None
    if result.returncode == 0:
        scenes = parse_plan_scenes(result.stdout)
        if scenes is None:
            return None
        return PlanRun(result.stdout.encode("utf-8"), scenes, script_revision(data))
    return parse_plan_failure(result.stderr, temp_path)


def run_plan(
    data: bytes, run: Callable[..., CliResult], launch_dir: Path, lock: threading.Lock, timeout: float = 10.0
) -> PlanRun | PlanProblem | None:
    """Run `plan --progress json` ONCE on `data`: the one shared plan runner of the detail reader and the start route.

    The bytes go to a private 0600 temp file in the launch directory, deleted afterwards; the temp path never leaves
    this function. The shared check lock is held for the whole run. Returns the passed plan (the exact stdout bytes,
    its scenes and the script revision), the one script problem, or None for a CLI failure (timeout, crash, another
    kind of failure, a plan that is not the expected shape).
    """
    with lock:
        descriptor, temp_path = tempfile.mkstemp(prefix="plan-", suffix=".md", dir=launch_dir)  # exclusive, 0600
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
            # the argv item and the prefix to strip are the same str: the CLI echoes the argv string exactly
            return _outcome(run(["plan", "--progress", "json", temp_path], None, timeout), temp_path, data)
        finally:
            os.unlink(temp_path)
