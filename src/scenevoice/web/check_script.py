import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from .cli_result import CliResult
from .error_envelope import error_envelope
from .json_response import json_response
from .parse_plan_failure import parse_plan_failure
from .plan_scene_count import plan_scene_count
from .project_dir import project_dir
from .request import Request
from .response import Response
from .route_table import Handler
from .with_root import with_root

NEEDS_TEXT = "Send the script as text."
CHECK_FAILED = "The script could not be checked just now. Try again."
CHECK_TIMEOUT = 10.0


def _outcome(result: CliResult, temp_path: str) -> Response:
    if result.timed_out or result.returncode == -1:
        return error_envelope("cli_failed", CHECK_FAILED)
    if result.returncode == 0:
        scenes = plan_scene_count(result.stdout)
        if scenes is None:
            return error_envelope("cli_failed", CHECK_FAILED)
        return json_response(200, {"ok": True, "scenes": scenes})
    problem = parse_plan_failure(result.stderr, temp_path)
    if problem is None:
        return error_envelope("cli_failed", CHECK_FAILED)
    return json_response(200, {"ok": False, "problems": [{"line": problem.line, "message": problem.message}]})


def _check(data: bytes, run: Callable[..., CliResult], launch_dir: Path, timeout: float) -> Response:
    descriptor, temp_path = tempfile.mkstemp(prefix="check-", suffix=".md", dir=launch_dir)  # exclusive, 0600
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        # the argv item and the prefix to strip are the same str: the CLI echoes the argv string exactly
        return _outcome(run(["plan", "--progress", "json", temp_path], None, timeout), temp_path)
    finally:
        os.unlink(temp_path)


def check_script(
    root_getter: Callable[[], Path],
    project_id: str,
    run: Callable[..., CliResult],
    launch_dir: Path,
    lock: threading.Lock,
    timeout: float = CHECK_TIMEOUT,
) -> Handler:
    """POST /api/projects/{id}/check with {"text": str}: run `plan` on the unsaved text, never on the saved file.

    The text goes to a private temp file in the launch directory (never the workspace), is deleted afterwards, and the
    temp path is never part of a response. One server-wide lock serialises checks; the text is never logged.
    """

    def handle(request: Request) -> Response:
        body = request.json_body
        text = body.get("text") if isinstance(body, dict) else None
        if not isinstance(text, str):
            return error_envelope("bad_request", NEEDS_TEXT)
        try:
            data = text.encode("utf-8")
        except UnicodeEncodeError:  # a lone surrogate from a JSON escape
            return error_envelope("bad_request", NEEDS_TEXT)

        def use(root: Path) -> Response:
            if project_dir(root, project_id) is None:
                return error_envelope("not_found", "That project does not exist.")
            with lock:
                return _check(data, run, launch_dir, timeout)

        return with_root(root_getter, use)

    return handle
