from collections.abc import Callable
from pathlib import Path

from .error_envelope import error_envelope
from .exact_entry import exact_entry
from .json_response import json_response
from .project_dir import project_dir
from .read_regular_bytes import read_regular_bytes
from .request import Request
from .response import Response
from .route_table import Handler
from .with_root import with_root
from .workspace_error import FileTooLargeError

SCRIPT_CAP = 1_048_576
UNREADABLE = "The script in this project is not an ordinary text file, so it cannot be opened here."
TOO_LARGE = "The script in this project is larger than 1 MiB, so it cannot be opened here."
NOT_UTF8 = "The script in this project is not valid UTF-8 text, so it cannot be opened here."


def _read(directory: Path, key_file: Path | None) -> Response:
    if not exact_entry(directory, "script.md"):  # absent, or only a differently spelled twin: a new script
        return json_response(200, {"text": ""})
    try:
        data = read_regular_bytes(directory / "script.md", SCRIPT_CAP, key_file)
    except FileTooLargeError:
        return error_envelope("bad_request", TOO_LARGE)
    if data is None:
        return error_envelope("bad_request", UNREADABLE)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return error_envelope("bad_request", NOT_UTF8)
    return json_response(200, {"text": text})


def get_script(root_getter: Callable[[], Path], project_id: str, key_file: Path | None) -> Handler:
    """GET /api/projects/{id}/script: the exact text of `script.md`, `""` when it is absent; writes nothing."""

    def handle(request: Request) -> Response:
        def use(root: Path) -> Response:
            directory = project_dir(root, project_id)
            if directory is None:
                return error_envelope("not_found", "That project does not exist.")
            return _read(directory, key_file)

        return with_root(root_getter, use)

    return handle
