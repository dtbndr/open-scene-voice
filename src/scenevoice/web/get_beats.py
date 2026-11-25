import json
from collections.abc import Callable
from pathlib import Path

from .beats_light_check import beats_light_check
from .error_envelope import error_envelope
from .job_availability import NO_BEATS
from .project_dir import project_dir
from .read_beats_state import BEATS_CAP
from .read_json_file import read_json_file
from .request import Request
from .response import Response
from .route_table import Handler
from .with_root import with_root

UNREADABLE = "The beats in this project could not be read, so they are not shown."


def _read(directory: Path, key_file: Path | None) -> Response:
    read = read_json_file(directory, "beats.json", BEATS_CAP, key_file)
    if read.state == "none":
        return error_envelope("not_found", NO_BEATS)
    if read.state != "ok" or beats_light_check(read.value) is None:
        return error_envelope("bad_request", UNREADABLE)
    try:  # a NaN or lone surrogate nested in a scene is not a body a browser can parse
        body = json.dumps(read.value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, UnicodeEncodeError):
        return error_envelope("bad_request", UNREADABLE)
    return Response(200, body, (("Content-Type", "application/json; charset=utf-8"),), no_store=True)


def get_beats(root_getter: Callable[[], Path], project_id: str, key_file: Path | None) -> Handler:
    """GET /api/projects/{id}/beats: the sidecar `beats.json` as parsed, only when it passes the light check.

    Never says fresh or stale (the detail's `beats.state` does); writes nothing.
    """

    def handle(request: Request) -> Response:
        def use(root: Path) -> Response:
            directory = project_dir(root, project_id)
            if directory is None:
                return error_envelope("not_found", "That project does not exist.")
            return _read(directory, key_file)

        return with_root(root_getter, use)

    return handle
