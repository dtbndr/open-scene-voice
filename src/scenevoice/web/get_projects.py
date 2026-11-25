from collections.abc import Callable
from pathlib import Path

from .error_envelope import error_envelope
from .json_response import json_response
from .list_projects import list_projects
from .request import Request
from .response import Response
from .route_table import Handler
from .with_root import with_root

DOCUMENTS_DENIED = (
    "SceneVoice could not open your Documents folder. Open System Settings, Privacy and Security, "
    "Files and Folders, and allow Terminal, then try again."
)


def get_projects(root_getter: Callable[[], Path]) -> Handler:
    """GET /api/projects: the resolved workspace path and its projects; nothing is created or changed."""

    def handle(request: Request) -> Response:
        try:
            return with_root(
                root_getter, lambda root: json_response(200, {"workspace": str(root), "projects": list_projects(root)})
            )
        except PermissionError:  # macOS denied the Documents prompt: say so instead of "Something went wrong."
            return error_envelope("internal_error", DOCUMENTS_DENIED)

    return handle
