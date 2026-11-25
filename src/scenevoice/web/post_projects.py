from collections.abc import Callable
from pathlib import Path

from .error_envelope import error_envelope
from .get_projects import DOCUMENTS_DENIED
from .json_response import json_response
from .make_project import make_project
from .request import Request
from .response import Response
from .route_table import Handler
from .with_root import with_root

_MAX_NAME = 200
NEEDS_NAME = "Give the project a name of 1 to 200 characters."


def post_projects(root_getter: Callable[[], Path]) -> Handler:
    """POST /api/projects with {"name": str}: create the folder only, answer 201 with its id."""

    def handle(request: Request) -> Response:
        body = request.json_body
        name = body.get("name") if isinstance(body, dict) else None
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= _MAX_NAME:
            return error_envelope("bad_request", NEEDS_NAME)
        try:
            return with_root(root_getter, lambda root: json_response(201, {"id": make_project(root, name.strip())}))
        except PermissionError:
            return error_envelope("internal_error", DOCUMENTS_DENIED)

    return handle
