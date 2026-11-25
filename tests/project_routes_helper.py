"""The one place tests build `ProjectRoutes`: later slices add constructor arguments here."""

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scenevoice.web import JobEvents, JobRunner, ProjectRoutes


def make_project_routes(**options: Any) -> ProjectRoutes:
    """Build `ProjectRoutes` with safe defaults: a recording launcher, a fresh launch directory, an idle runner and event hub, no key file."""
    launched: list[list[str]] = []

    def record(argv: list[str]) -> int:
        launched.append(list(argv))
        return 0

    root_getter: Callable[[], Path] = options.pop("root_getter", lambda: None)
    launch_dir = options.pop("launch_dir", None) or Path(tempfile.mkdtemp(prefix="scenevoice-launch-"))
    arguments: dict[str, Any] = {
        "root_getter": root_getter,
        "run": None,
        "key_file": None,
        "launch": record,
        "launch_dir": launch_dir,
        "job_active": lambda: False,
        "runner": JobRunner(cwd=launch_dir, env={}),
        "events": JobEvents(),
    }
    return ProjectRoutes(**{**arguments, **options})
