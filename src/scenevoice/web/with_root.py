from collections.abc import Callable
from pathlib import Path

from .error_envelope import error_envelope
from .response import Response
from .workspace_error import WorkspaceKeyFileError


def with_root(root_getter: Callable[[], Path], use: Callable[[Path], Response]) -> Response:
    """Run `use` with the workspace root; a workspace that holds the key file is a plain 400 for every route."""
    try:
        root = root_getter()
    except WorkspaceKeyFileError as error:
        return error_envelope("bad_request", str(error))
    return use(root)
