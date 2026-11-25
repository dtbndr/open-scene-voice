import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from .error_envelope import error_envelope
from .json_response import json_response
from .project_dir import project_dir
from .request import Request
from .response import Response
from .reveal_argv import reveal_argv
from .route_table import Handler
from .with_root import with_root

NO_PROJECT = "There is no project with that name."
UNSUPPORTED = "Show in Finder works on macOS and Linux only. Open the project folder yourself."
REVEAL_FAILED = "The folder could not be opened just now. Try again."


def post_reveal(
    root_getter: Callable[[], Path],
    project_id: str,
    launch: Callable[[Sequence[str]], int],
    platform: str | None = None,
) -> Handler:
    """POST /api/projects/{id}/reveal: start the platform opener on the project folder; the body is ignored.

    The one route that starts a program. The only argument is the validated absolute project directory, `launch` is
    the injected launcher (exit code, non-zero on failure), and `platform` (default `sys.platform`, read at the call)
    picks the opener. Nothing is launched for a missing project or an unsupported platform; no message names a path.
    """

    def handle(request: Request) -> Response:
        def use(root: Path) -> Response:
            directory = project_dir(root, project_id)
            if directory is None:
                return error_envelope("not_found", NO_PROJECT)
            argv = reveal_argv(platform if platform is not None else sys.platform, str(directory))
            if argv is None:
                return error_envelope("unsupported", UNSUPPORTED)
            try:
                code = launch(argv)
            except OSError:
                return error_envelope("cli_failed", REVEAL_FAILED)
            if code != 0:
                return error_envelope("cli_failed", REVEAL_FAILED)
            return json_response(200, {"ok": True})

        return with_root(root_getter, use)

    return handle
