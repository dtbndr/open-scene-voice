import threading
from collections.abc import Callable
from pathlib import Path

from .busy_message import busy_message
from .error_envelope import error_envelope
from .job_runner import JobRunner
from .json_response import json_response
from .project_dir import project_dir
from .request import Request
from .response import Response
from .route_table import Handler
from .spelling_conflict import spelling_conflict
from .with_root import with_root
from .workspace_error import WorkspaceError
from .write_file_atomic import write_file_atomic

NEEDS_TEXT = "Send the script as text."
SPELLING = "This project folder holds a file spelled Script.md. Rename it, then save again."


def _save(directory: Path, text: str, key_file: Path | None) -> Response:
    if spelling_conflict(directory, "script.md"):  # before any write: a replace could hit the other spelling
        return error_envelope("bad_request", SPELLING)
    try:
        write_file_atomic(directory, "script.md", text.encode("utf-8"), key_file)
    except WorkspaceError as error:
        return error_envelope("bad_request", str(error))
    return json_response(200, {"saved": True})


def put_script(
    root_getter: Callable[[], Path], project_id: str, key_file: Path | None, runner: JobRunner, script_lock: threading.Lock
) -> Handler:
    """PUT /api/projects/{id}/script with {"text": str}: replace `script.md` with the exact UTF-8 bytes.

    Never looks at the content (the check route does); a concurrent save is last-writer-wins by design. While any job
    holds the slot (in every project, J2) the save is 409 `busy`; the busy check and the write both run under the script
    lock, the one `post_job` holds while it reads `script.md`, so a save either lands before a start's read or is refused.
    """

    def handle(request: Request) -> Response:
        body = request.json_body
        text = body.get("text") if isinstance(body, dict) else None
        if not isinstance(text, str):
            return error_envelope("bad_request", NEEDS_TEXT)

        def use(root: Path) -> Response:
            directory = project_dir(root, project_id)
            if directory is None:
                return error_envelope("not_found", "That project does not exist.")
            with script_lock:
                if runner.job_active():
                    return error_envelope("busy", busy_message(runner.busy_reason()))
                return _save(directory, text, key_file)

        return with_root(root_getter, use)

    return handle
